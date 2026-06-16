import uuid
from typing import Optional

from sqlmodel import SQLModel


class QueryRequest(SQLModel):
    question: str
    conversation_id: Optional[uuid.UUID] = None   # pass to continue a thread


class SourceChunk(SQLModel):
    chunk_id: str
    doc_id: Optional[str] = None
    corpus_name: Optional[str] = None
    section_path: Optional[str] = None
    page_num: Optional[int] = None
    relevance_score: float
    text_excerpt: str


class QueryMetadata(SQLModel):
    query_id: str
    corpus_searched: str
    hyde_applied: bool
    sub_queries_generated: int
    chunks_retrieved: int
    chunks_after_rerank: int
    latency_ms: int


class QueryResponse(SQLModel):
    answer: str
    sources: list[SourceChunk]
    metadata: QueryMetadata
    conversation_id: uuid.UUID
