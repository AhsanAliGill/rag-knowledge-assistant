import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlmodel import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.config.rag_settings import rag_settings
from app.models.chunk import ChunkType, RAGChunk
from app.models.document import CorpusType, DocumentStatus, RAGDocument
from app.models.ingestion_job import JobStatus, RAGIngestionJob
from app.services.rag.evaluation.ground_truth_loader import GroundTruthStore
from app.services.rag.ingestion.bm25_keyword_indexer import BM25Indexer
from app.services.rag.ingestion.ingestion_runner import IngestionJobManager
from app.services.rag.ingestion.qdrant_indexer import VectorIndexer
from app.schemas.document import (
    DocumentDetailRead,
    DocumentListResponse,
    DocumentRead,
    DocumentUploadResponse,
    GroundTruthUploadResponse,
    JobStatusResponse,
)


async def upload_document(
    file: UploadFile,
    description: str | None,
    user_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession,
) -> DocumentUploadResponse:
    content = await file.read()

    if len(content) > rag_settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 50 MB limit.")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF files are accepted.")

    sha256 = hashlib.sha256(content).hexdigest()

    existing = await session.exec(
        select(RAGDocument).where(RAGDocument.sha256 == sha256, RAGDocument.user_id == user_id)
    )
    if existing.first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This document already exists in your corpus.")

    upload_dir = Path(rag_settings.UPLOAD_DIR) / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    storage_path = upload_dir / f"{doc_id}_{file.filename}"
    storage_path.write_bytes(content)

    doc = RAGDocument(
        id=doc_id,
        user_id=user_id,
        filename=file.filename,
        corpus_name=file.filename,
        description=description,
        status=DocumentStatus.PENDING,
        corpus_type=CorpusType.USER,
        size_bytes=len(content),
        sha256=sha256,
        storage_path=str(storage_path),
    )
    session.add(doc)

    job = RAGIngestionJob(doc_id=doc_id, user_id=user_id)
    session.add(job)
    await session.flush()   # all fields have Python-side defaults; no refresh needed
    await session.commit()

    background_tasks.add_task(_run_ingestion, job.id, session)

    return DocumentUploadResponse(
        doc_id=doc_id,
        job_id=job.id,
        status="queued",
        message="Document accepted. Use job_id to track ingestion progress.",
    )


async def _run_ingestion(job_id: uuid.UUID, session: AsyncSession) -> None:
    manager = IngestionJobManager(session)
    await manager.run(job_id)


async def list_documents(
    filter_status: str | None,
    limit: int,
    offset: int,
    session: AsyncSession,
) -> DocumentListResponse:
    query = select(RAGDocument)
    if filter_status:
        try:
            query = query.where(RAGDocument.status == DocumentStatus(filter_status))
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid status: {filter_status}")

    total_result = await session.exec(
        select(func.count()).select_from(RAGDocument)
    )
    total = total_result.one()

    result = await session.exec(query.offset(offset).limit(limit))
    docs = result.all()

    return DocumentListResponse(
        documents=[_to_read(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_document(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> DocumentDetailRead:
    doc = await _get_owned_doc(doc_id, user_id, session)

    parent_count = await session.exec(
        select(func.count()).select_from(RAGChunk).where(
            RAGChunk.doc_id == doc_id, RAGChunk.chunk_type == ChunkType.PARENT
        )
    )
    child_count = await session.exec(
        select(func.count()).select_from(RAGChunk).where(
            RAGChunk.doc_id == doc_id, RAGChunk.chunk_type != ChunkType.PARENT
        )
    )

    return DocumentDetailRead(
        doc_id=doc.id,
        corpus_name=doc.corpus_name,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
        ready_at=doc.ready_at,
        parent_chunks=parent_count.one(),
        child_chunks=child_count.one(),
        sha256=doc.sha256,
    )


async def delete_document(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    doc = await _get_owned_doc(doc_id, user_id, session)

    indexer = VectorIndexer()
    await indexer.delete_by_doc_id(str(doc_id))

    namespace = f"user_{user_id}"
    await asyncio.to_thread(BM25Indexer().delete_by_doc_id, namespace, str(doc_id))

    await session.exec(delete(RAGChunk).where(RAGChunk.doc_id == doc_id))
    await session.exec(delete(RAGIngestionJob).where(RAGIngestionJob.doc_id == doc_id))

    storage = Path(doc.storage_path)
    if storage.exists():
        storage.unlink()

    await session.exec(delete(RAGDocument).where(RAGDocument.id == doc_id))
    await session.commit()

    return {"message": "Document and all associated data deleted.", "doc_id": str(doc_id)}


async def upload_ground_truth(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    pairs: list[dict],
    session: AsyncSession,
) -> GroundTruthUploadResponse:
    await _get_owned_doc(doc_id, user_id, session)

    if len(pairs) > 200:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Maximum 200 Q&A pairs per upload.")

    store = GroundTruthStore()
    store.save(str(doc_id), pairs)

    return GroundTruthUploadResponse(
        doc_id=doc_id,
        qa_count=len(pairs),
        message="Ground truth saved. Ready for evaluation.",
    )


async def get_job_status(
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> JobStatusResponse:
    job = await session.get(RAGIngestionJob, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")

    estimated = None
    if job.status == JobStatus.PROCESSING and job.progress > 0:
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        rate = job.progress / elapsed if elapsed > 0 else 1
        estimated = int((100 - job.progress) / rate) if rate > 0 else None

    return JobStatusResponse(
        job_id=job.id,
        doc_id=job.doc_id,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        estimated_completion_seconds=estimated,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


def _to_read(doc: RAGDocument) -> DocumentRead:
    return DocumentRead(
        doc_id=doc.id,
        corpus_name=doc.corpus_name,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
        ready_at=doc.ready_at,
    )


async def _get_owned_doc(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> RAGDocument:
    doc = await session.get(RAGDocument, doc_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    if doc.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied.")
    return doc
