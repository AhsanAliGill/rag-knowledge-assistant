import uuid

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.controllers import conversation_controller as ctrl
from app.schemas.conversation import ConversationHistory, ConversationSummary

router = APIRouter(prefix="/rag/conversations", tags=["Conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.list_conversations(user_id=current_user.id, session=session)


@router.get("/{conversation_id}", response_model=ConversationHistory)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.get_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
        session=session,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    await ctrl.delete_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
        session=session,
    )
