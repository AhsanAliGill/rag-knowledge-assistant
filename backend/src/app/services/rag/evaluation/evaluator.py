import time
import uuid
from datetime import datetime, timezone

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.evaluation import EvalStatus, RAGEvaluation, RAGEvaluationResult
from app.services.rag.evaluation.ground_truth_loader import GroundTruthStore
from app.services.rag.evaluation.metrics import RAGMetricsEvaluator
from app.services.rag.pipeline import RAGPipeline


class EvaluationRunner:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = GroundTruthStore()
        self._metrics = RAGMetricsEvaluator()

    async def run(self, eval_id: uuid.UUID) -> None:
        evaluation = await self._session.get(RAGEvaluation, eval_id)

        evaluation.status = EvalStatus.PROCESSING
        self._session.add(evaluation)
        await self._session.commit()

        try:
            qa_pairs = self._store.load(str(evaluation.doc_id))
            pipeline = RAGPipeline(self._session)

            namespace = f"user_{evaluation.user_id}"

            scores_sum = {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0, "context_recall": 0.0}

            for i, qa in enumerate(qa_pairs):
                t0 = time.monotonic()
                result = await pipeline.query(
                    question=qa.question,
                    namespace=namespace,
                    doc_id=str(evaluation.doc_id),
                )
                latency_ms = int((time.monotonic() - t0) * 1000)

                contexts = [s.page_content for s in result.sources]
                metric = await self._metrics.evaluate_single(
                    question=qa.question,
                    generated_answer=result.answer,
                    contexts=contexts,
                    ground_truth=qa.expected_answer,
                )

                source_found = any(
                    qa.source_section and qa.source_section in (s.metadata.get("section_path") or "")
                    for s in result.sources
                )

                db_result = RAGEvaluationResult(
                    eval_id=eval_id,
                    question=qa.question,
                    expected_answer=qa.expected_answer,
                    generated_answer=result.answer,
                    faithfulness=metric.faithfulness,
                    answer_relevancy=metric.answer_relevancy,
                    context_precision=metric.context_precision,
                    context_recall=metric.context_recall,
                    source_found=source_found,
                    source_section=qa.source_section,
                    latency_ms=latency_ms,
                )
                self._session.add(db_result)

                for k in scores_sum:
                    scores_sum[k] += getattr(metric, k)

                evaluation.qa_done = i + 1
                self._session.add(evaluation)
                await self._session.commit()

            n = len(qa_pairs) or 1
            evaluation.faithfulness = scores_sum["faithfulness"] / n
            evaluation.answer_relevancy = scores_sum["answer_relevancy"] / n
            evaluation.context_precision = scores_sum["context_precision"] / n
            evaluation.context_recall = scores_sum["context_recall"] / n
            evaluation.overall = sum(scores_sum.values()) / (4 * n)
            evaluation.status = EvalStatus.COMPLETED
            evaluation.completed_at = datetime.now(timezone.utc)
            self._session.add(evaluation)
            await self._session.commit()

        except Exception as exc:
            evaluation.status = EvalStatus.FAILED
            evaluation.error_message = str(exc)[:2000]
            self._session.add(evaluation)
            await self._session.commit()
            raise
