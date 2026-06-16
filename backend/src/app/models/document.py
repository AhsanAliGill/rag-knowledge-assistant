import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class CorpusType(str, Enum):
    DEFAULT = "default"
    USER = "user"


class RAGDocument(SQLModel, table=True):
    __tablename__ = "rag_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id", index=True)
    filename: str = Field(max_length=255)
    corpus_name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)
    corpus_type: CorpusType = Field(default=CorpusType.USER)
    page_count: Optional[int] = Field(default=None)
    chunk_count: Optional[int] = Field(default=None)
    size_bytes: int = Field(default=0)
    sha256: str = Field(max_length=64, index=True)
    storage_path: str = Field(max_length=512)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    ready_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
