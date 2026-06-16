import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class ChunkType(str, Enum):
    PARENT = "parent"
    CHILD = "child"
    TABLE_ROW = "table_row"


class RAGChunk(SQLModel, table=True):
    __tablename__ = "rag_chunks"

    id: str = Field(primary_key=True)
    doc_id: uuid.UUID = Field(foreign_key="rag_documents.id", index=True)
    user_id: Optional[uuid.UUID] = Field(default=None, index=True)
    chunk_type: ChunkType = Field(default=ChunkType.CHILD)
    parent_id: Optional[str] = Field(default=None, index=True)
    child_index: Optional[int] = Field(default=None)
    text: str = Field(sa_column=Column(Text, nullable=False))
    section_path: Optional[str] = Field(default=None, max_length=500)
    page_num: Optional[int] = Field(default=None)
    page_range: Optional[str] = Field(default=None, max_length=20)
    vector_id: Optional[str] = Field(default=None, max_length=255)
    token_count: int = Field(default=0)
