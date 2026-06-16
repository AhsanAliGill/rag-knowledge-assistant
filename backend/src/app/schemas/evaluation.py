import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel


class EvaluationRequest(SQLModel):
    doc_id: uuid.UUID


class EvaluationScores(SQLModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    overall: float


class EvaluationPassFail(SQLModel):
    faithfulness: str
    answer_relevancy: str
    context_precision: str
    context_recall: str
    overall: str


class PerQuestionResult(SQLModel):
    question: str
    expected_answer: str
    generated_answer: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    source_found: bool
    source_section: Optional[str] = None
    latency_ms: int


class EvaluationTriggerResponse(SQLModel):
    eval_id: uuid.UUID
    status: str
    qa_count: int
    message: str


class EvaluationStatusResponse(SQLModel):
    eval_id: uuid.UUID
    doc_id: uuid.UUID
    status: str
    progress: int
    qa_total: int
    qa_done: int


class EvaluationReport(SQLModel):
    eval_id: uuid.UUID
    doc_id: uuid.UUID
    status: str
    qa_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    scores: Optional[EvaluationScores] = None
    pass_fail: Optional[EvaluationPassFail] = None
    thresholds_used: Optional[EvaluationScores] = None
    per_question_results: Optional[list[PerQuestionResult]] = None


class EvaluationListItem(SQLModel):
    eval_id: uuid.UUID
    doc_id: uuid.UUID
    status: str
    overall: Optional[float] = None
    qa_count: int
    created_at: datetime


class EvaluationListResponse(SQLModel):
    evaluations: list[EvaluationListItem]
    total: int
