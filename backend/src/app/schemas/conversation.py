import uuid
from datetime import datetime

from sqlmodel import SQLModel


class MessageItem(SQLModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ConversationSummary(SQLModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationHistory(SQLModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageItem]
