from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.controllers import query_controller as ctrl
from app.db.session import get_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/rag", tags=["RAG Query"])


@router.post("/query", response_model=QueryResponse)
async def ask(
    request: QueryRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await ctrl.query(request=request, user_id=current_user.id, session=session)


@router.post("/query/stream")
async def ask_stream(
    request: QueryRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return StreamingResponse(
        ctrl.query_stream(request=request, user_id=current_user.id, session=session),
        media_type="application/x-ndjson",
    )
