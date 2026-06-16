import json
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import HTTPException, status
from qdrant_client.http.exceptions import UnexpectedResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.conversation import RAGConversation, RAGConversationMessage
from app.schemas.query import QueryMetadata, QueryRequest, QueryResponse, SourceChunk
from app.services.rag.pipeline import RAGPipeline


async def query(
    request: QueryRequest,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> QueryResponse:
    if not request.question or not request.question.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Question must not be empty.")
    if len(request.question) > 1000:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Question must be under 1000 characters."
        )

    # ── Conversation: load or create ─────────────────────────────────────────
    conversation = await _get_or_create_conversation(
        conversation_id=request.conversation_id,
        user_id=user_id,
        first_question=request.question,
        session=session,
    )

    # Load prior messages as history (oldest first, cap at 20 turns = 10 exchanges)
    history = await _load_history(conversation.id, session, limit=20)

    # ── RAG ──────────────────────────────────────────────────────────────────
    namespace = "shared"
    pipeline = RAGPipeline(session)

    try:
        result = await pipeline.query(
            question=request.question,
            namespace=namespace,
            doc_id=None,
            history=history,
        )
    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No documents found. Please upload a document before querying.",
            )
        raise

    # ── Persist user message + assistant reply ────────────────────────────────
    now = datetime.utcnow()
    session.add(
        RAGConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=request.question,
            created_at=now,
        )
    )
    session.add(
        RAGConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result.answer,
            created_at=now,
        )
    )
    conversation.updated_at = now
    session.add(conversation)
    await session.commit()

    # ── Build response ────────────────────────────────────────────────────────
    sources: list[SourceChunk] = [
        SourceChunk(
            chunk_id=s.metadata.get("chunk_id", ""),
            doc_id=s.metadata.get("doc_id"),
            corpus_name=s.metadata.get("corpus_type", s.metadata.get("namespace", "")),
            section_path=s.metadata.get("section_path"),
            page_num=s.metadata.get("page_num") or s.metadata.get("page_number"),
            relevance_score=float(s.metadata.get("relevance_score", 0.0)),
            text_excerpt=s.page_content[:400],
        )
        for s in result.sources
    ]

    return QueryResponse(
        answer=result.answer,
        sources=sources,
        conversation_id=conversation.id,
        metadata=QueryMetadata(
            query_id=result.query_id,
            corpus_searched=result.corpus_searched,
            hyde_applied=result.hyde_applied,
            sub_queries_generated=result.sub_queries_generated,
            chunks_retrieved=result.chunks_retrieved,
            chunks_after_rerank=result.chunks_after_rerank,
            latency_ms=result.latency_ms,
        ),
    )


async def query_stream(
    request: QueryRequest,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> AsyncGenerator[bytes, None]:
    """Async generator that yields NDJSON bytes for SSE streaming.

    IMPORTANT: this generator must NEVER raise. StreamingResponse sends
    'HTTP 200 + Transfer-Encoding: chunked' before the first iteration,
    so any unhandled exception kills the TCP connection mid-stream and the
    browser sees ERR_INCOMPLETE_CHUNKED_ENCODING. All errors are yielded as
    {"type": "error"} events so the stream closes cleanly.
    """

    def _err(msg: str) -> bytes:
        return (json.dumps({"type": "error", "message": msg}) + "\n").encode()

    # ── Validate before touching the DB ──────────────────────────────────────
    if not request.question or not request.question.strip():
        yield _err("Question must not be empty.")
        return
    if len(request.question) > 1000:
        yield _err("Question must be under 1000 characters.")
        return

    # ── Conversation lookup / creation ────────────────────────────────────────
    try:
        conversation = await _get_or_create_conversation(
            conversation_id=request.conversation_id,
            user_id=user_id,
            first_question=request.question,
            session=session,
        )
        history = await _load_history(conversation.id, session, limit=20)
    except HTTPException as exc:
        yield _err(exc.detail)
        return
    except Exception as exc:
        yield _err(f"Failed to load conversation: {exc}")
        return

    # Send conversation_id immediately so frontend can update the sidebar
    yield (json.dumps({"type": "start", "conversation_id": str(conversation.id)}) + "\n").encode()

    namespace = "shared"
    pipeline = RAGPipeline(session)
    collected_tokens: list[str] = []

    # ── RAG streaming ─────────────────────────────────────────────────────────
    try:
        async for event in pipeline.query_stream(
            question=request.question,
            namespace=namespace,
            doc_id=None,
            history=history,
        ):
            if event["type"] == "token":
                collected_tokens.append(event["content"])
            yield (json.dumps(event) + "\n").encode()
    except UnexpectedResponse as exc:
        msg = (
            "No documents found. Please upload a document first."
            if exc.status_code == 404
            else f"Vector DB error ({exc.status_code})."
        )
        yield _err(msg)
        return
    except Exception as exc:
        yield _err(f"Generation failed: {exc}")
        return

    # ── Persist after stream completes ────────────────────────────────────────
    full_answer = "".join(collected_tokens)
    if not full_answer:
        return

    try:
        now = datetime.utcnow()
        session.add(
            RAGConversationMessage(
                conversation_id=conversation.id,
                role="user",
                content=request.question,
                created_at=now,
            )
        )
        session.add(
            RAGConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=full_answer,
                created_at=now,
            )
        )
        conversation.updated_at = now
        session.add(conversation)
        await session.commit()
    except Exception:
        # Answer was already streamed to the user — don't break the stream.
        # The conversation simply won't be persisted this turn.
        await session.rollback()


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_or_create_conversation(
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID,
    first_question: str,
    session: AsyncSession,
) -> RAGConversation:
    if conversation_id:
        conv = await session.get(RAGConversation, conversation_id)
        if not conv or conv.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
        return conv

    title = first_question[:100].strip()
    conv = RAGConversation(user_id=user_id, title=title)
    session.add(conv)
    await session.flush()  # populate conv.id before we use it
    return conv


async def _load_history(
    conversation_id: uuid.UUID,
    session: AsyncSession,
    limit: int = 20,
) -> list[dict]:
    result = await session.exec(
        select(RAGConversationMessage)
        .where(RAGConversationMessage.conversation_id == conversation_id)
        .order_by(RAGConversationMessage.created_at.asc(), RAGConversationMessage.role.desc())
        .limit(limit)
    )
    msgs = result.all()
    return [{"role": m.role, "content": m.content} for m in msgs]
