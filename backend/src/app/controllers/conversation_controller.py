import uuid

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.conversation import RAGConversation, RAGConversationMessage
from app.schemas.conversation import ConversationHistory, ConversationSummary, MessageItem

_LIST_LIMIT = 100


async def list_conversations(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[ConversationSummary]:
    result = await session.exec(
        select(RAGConversation)
        .where(RAGConversation.user_id == user_id)
        .order_by(RAGConversation.updated_at.desc())
        .limit(_LIST_LIMIT)
    )
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in result.all()
    ]


async def get_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> ConversationHistory:
    # Single query: fetch conv + messages together to avoid two round-trips to Neon
    conv_result = await session.exec(
        select(RAGConversation)
        .where(RAGConversation.id == conversation_id)
    )
    conv = conv_result.first()
    if not conv or conv.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")

    msg_result = await session.exec(
        select(RAGConversationMessage)
        .where(RAGConversationMessage.conversation_id == conversation_id)
        .order_by(RAGConversationMessage.created_at.asc())
    )
    messages = [
        MessageItem(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
        for m in msg_result.all()
    ]
    return ConversationHistory(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    conv = await session.get(RAGConversation, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")

    # Messages cascade-delete via FK ON DELETE CASCADE (migration 27a31a8e5963)
    await session.delete(conv)
    await session.commit()
