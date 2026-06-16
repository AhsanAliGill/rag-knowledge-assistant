import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.controllers import evaluation_controller as ctrl
from app.schemas.evaluation import (
    EvaluationListResponse,
    EvaluationReport,
    EvaluationRequest,
    EvaluationStatusResponse,
    EvaluationTriggerResponse,
)

router = APIRouter(prefix="/rag/evaluations", tags=["RAG Evaluation"])


@router.post("", response_model=EvaluationTriggerResponse, status_code=202)
async def trigger_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.trigger_evaluation(
        doc_id=request.doc_id,
        user_id=current_user.id,
        background_tasks=background_tasks,
        session=session,
    )


@router.get("/{eval_id}")
async def get_evaluation(
    eval_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.get_evaluation_status(
        eval_id=eval_id, user_id=current_user.id, session=session
    )


@router.get("", response_model=EvaluationListResponse)
async def list_evaluations(
    doc_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.list_evaluations(
        user_id=current_user.id,
        doc_id=doc_id,
        limit=limit,
        offset=offset,
        session=session,
    )
