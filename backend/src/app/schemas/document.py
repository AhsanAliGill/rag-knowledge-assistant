import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel

from app.models.document import DocumentStatus


class DocumentUploadResponse(SQLModel):
    doc_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    message: str


class DocumentRead(SQLModel):
    doc_id: uuid.UUID
    corpus_name: str
    filename: str
    status: DocumentStatus
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    size_bytes: int
    created_at: datetime
    ready_at: Optional[datetime] = None


class DocumentDetailRead(DocumentRead):
    parent_chunks: Optional[int] = None
    child_chunks: Optional[int] = None
    sha256: str


class DocumentListResponse(SQLModel):
    documents: list[DocumentRead]
    total: int
    limit: int
    offset: int


class GroundTruthItem(SQLModel):
    question: str
    expected_answer: str
    source_section: Optional[str] = None


class GroundTruthUploadResponse(SQLModel):
    doc_id: uuid.UUID
    qa_count: int
    message: str


class JobStatusResponse(SQLModel):
    job_id: uuid.UUID
    doc_id: uuid.UUID
    status: str
    progress: int
    message: Optional[str] = None
    estimated_completion_seconds: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
