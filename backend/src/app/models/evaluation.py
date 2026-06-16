import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


class EvalStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RAGEvaluation(SQLModel, table=True):
    __tablename__ = "rag_evaluations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    doc_id: uuid.UUID = Field(foreign_key="rag_documents.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    corpus: str = Field(default="user", max_length=20)
    status: EvalStatus = Field(default=EvalStatus.QUEUED)
    qa_count: int = Field(default=0)
    qa_done: int = Field(default=0)
    faithfulness: Optional[float] = Field(default=None)
    answer_relevancy: Optional[float] = Field(default=None)
    context_precision: Optional[float] = Field(default=None)
    context_recall: Optional[float] = Field(default=None)
    overall: Optional[float] = Field(default=None)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class RAGEvaluationResult(SQLModel, table=True):
    __tablename__ = "rag_evaluation_results"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    eval_id: uuid.UUID = Field(foreign_key="rag_evaluations.id", index=True)
    question: str = Field(sa_column=Column(Text, nullable=False))
    expected_answer: str = Field(sa_column=Column(Text, nullable=False))
    generated_answer: str = Field(sa_column=Column(Text, nullable=False))
    faithfulness: float = Field(default=0.0)
    answer_relevancy: float = Field(default=0.0)
    context_precision: float = Field(default=0.0)
    context_recall: float = Field(default=0.0)
    source_found: bool = Field(default=False)
    source_section: Optional[str] = Field(default=None, max_length=255)
    latency_ms: int = Field(default=0)
