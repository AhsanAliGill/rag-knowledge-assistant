import uuid

from fastapi import BackgroundTasks, HTTPException, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.config.rag_settings import rag_settings
from app.models.document import DocumentStatus, RAGDocument
from app.models.evaluation import EvalStatus, RAGEvaluation, RAGEvaluationResult
from app.services.rag.evaluation.evaluator import EvaluationRunner
from app.services.rag.evaluation.ground_truth_loader import GroundTruthStore
from app.schemas.evaluation import (
    EvaluationListItem,
    EvaluationListResponse,
    EvaluationPassFail,
    EvaluationReport,
    EvaluationScores,
    EvaluationStatusResponse,
    EvaluationTriggerResponse,
    PerQuestionResult,
)


async def trigger_evaluation(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession,
) -> EvaluationTriggerResponse:
    doc = await session.get(RAGDocument, doc_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    if doc.status != DocumentStatus.READY:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Document is not ready.")

    store = GroundTruthStore()
    if not store.exists(str(doc_id)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No ground truth uploaded for this document.")

    qa_count = store.count(str(doc_id))
    evaluation = RAGEvaluation(doc_id=doc_id, user_id=user_id, qa_count=qa_count)
    session.add(evaluation)
    await session.flush()
    await session.commit()

    background_tasks.add_task(_run_evaluation, evaluation.id, session)

    return EvaluationTriggerResponse(
        eval_id=evaluation.id,
        status="queued",
        qa_count=qa_count,
        message=f"Evaluation queued. Will run all {qa_count} Q&A pairs.",
    )


async def _run_evaluation(eval_id: uuid.UUID, session: AsyncSession) -> None:
    runner = EvaluationRunner(session)
    await runner.run(eval_id)


async def get_evaluation_status(
    eval_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> EvaluationStatusResponse | EvaluationReport:
    evaluation = await session.get(RAGEvaluation, eval_id)
    if not evaluation or evaluation.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation not found.")

    if evaluation.status != EvalStatus.COMPLETED:
        return EvaluationStatusResponse(
            eval_id=evaluation.id,
            doc_id=evaluation.doc_id,
            status=evaluation.status.value,
            progress=int(evaluation.qa_done / evaluation.qa_count * 100) if evaluation.qa_count else 0,
            qa_total=evaluation.qa_count,
            qa_done=evaluation.qa_done,
        )

    results = await session.exec(
        select(RAGEvaluationResult).where(RAGEvaluationResult.eval_id == eval_id)
    )
    per_q = [
        PerQuestionResult(
            question=r.question,
            expected_answer=r.expected_answer,
            generated_answer=r.generated_answer,
            faithfulness=r.faithfulness,
            answer_relevancy=r.answer_relevancy,
            context_precision=r.context_precision,
            context_recall=r.context_recall,
            source_found=r.source_found,
            source_section=r.source_section,
            latency_ms=r.latency_ms,
        )
        for r in results.all()
    ]

    scores = EvaluationScores(
        faithfulness=evaluation.faithfulness or 0.0,
        answer_relevancy=evaluation.answer_relevancy or 0.0,
        context_precision=evaluation.context_precision or 0.0,
        context_recall=evaluation.context_recall or 0.0,
        overall=evaluation.overall or 0.0,
    )
    thresholds = EvaluationScores(
        faithfulness=rag_settings.EVAL_FAITHFULNESS_THRESHOLD,
        answer_relevancy=rag_settings.EVAL_RELEVANCY_THRESHOLD,
        context_precision=rag_settings.EVAL_PRECISION_THRESHOLD,
        context_recall=rag_settings.EVAL_RECALL_THRESHOLD,
        overall=rag_settings.EVAL_FAITHFULNESS_THRESHOLD,
    )
    pass_fail = EvaluationPassFail(
        faithfulness="pass" if scores.faithfulness >= thresholds.faithfulness else "fail",
        answer_relevancy="pass" if scores.answer_relevancy >= thresholds.answer_relevancy else "fail",
        context_precision="pass" if scores.context_precision >= thresholds.context_precision else "fail",
        context_recall="pass" if scores.context_recall >= thresholds.context_recall else "fail",
        overall="pass" if scores.overall >= thresholds.overall else "fail",
    )

    return EvaluationReport(
        eval_id=evaluation.id,
        doc_id=evaluation.doc_id,
        status=evaluation.status.value,
        qa_count=evaluation.qa_count,
        created_at=evaluation.created_at,
        completed_at=evaluation.completed_at,
        scores=scores,
        pass_fail=pass_fail,
        thresholds_used=thresholds,
        per_question_results=per_q,
    )


async def list_evaluations(
    user_id: uuid.UUID,
    doc_id: uuid.UUID | None,
    limit: int,
    offset: int,
    session: AsyncSession,
) -> EvaluationListResponse:
    query = select(RAGEvaluation).where(RAGEvaluation.user_id == user_id)
    if doc_id:
        query = query.where(RAGEvaluation.doc_id == doc_id)

    total_q = select(func.count()).select_from(RAGEvaluation).where(RAGEvaluation.user_id == user_id)
    if doc_id:
        total_q = total_q.where(RAGEvaluation.doc_id == doc_id)

    total = (await session.exec(total_q)).one()
    evals = (await session.exec(query.offset(offset).limit(limit))).all()

    return EvaluationListResponse(
        evaluations=[
            EvaluationListItem(
                eval_id=e.id,
                doc_id=e.doc_id,
                status=e.status.value,
                overall=e.overall,
                qa_count=e.qa_count,
                created_at=e.created_at,
            )
            for e in evals
        ],
        total=total,
    )
