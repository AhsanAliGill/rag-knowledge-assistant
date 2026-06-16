import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.controllers import document_controller as ctrl
from app.schemas.document import (
    DocumentDetailRead,
    DocumentListResponse,
    DocumentUploadResponse,
    GroundTruthItem,
    GroundTruthUploadResponse,
    JobStatusResponse,
)

router = APIRouter(prefix="/rag/documents", tags=["RAG Documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.upload_document(
        file=file,
        description=description,
        user_id=current_user.id,
        background_tasks=background_tasks,
        session=session,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    filter_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.list_documents(
        filter_status=filter_status,
        limit=limit,
        offset=offset,
        session=session,
    )


@router.get("/{doc_id}", response_model=DocumentDetailRead)
async def get_document(
    doc_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.get_document(doc_id=doc_id, user_id=current_user.id, session=session)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.delete_document(doc_id=doc_id, user_id=current_user.id, session=session)


@router.post("/{doc_id}/ground-truth", response_model=GroundTruthUploadResponse)
async def upload_ground_truth(
    doc_id: uuid.UUID,
    pairs: list[GroundTruthItem],
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.upload_ground_truth(
        doc_id=doc_id,
        user_id=current_user.id,
        pairs=[p.model_dump() for p in pairs],
        session=session,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.get_job_status(job_id=job_id, user_id=current_user.id, session=session)
