import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.utcnow()


class RAGConversation(SQLModel, table=True):
    __tablename__ = "rag_conversations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class RAGConversationMessage(SQLModel, table=True):
    __tablename__ = "rag_conversation_messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="rag_conversations.id", index=True)
    role: str = Field(max_length=16)        # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=_utcnow)
