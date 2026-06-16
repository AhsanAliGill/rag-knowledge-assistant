"""
RAG Pipeline — Orchestrator

Retrieval flow:
  [User Message + History]
          │
          ▼
  Query Rewriter LLM  ──► [NO_RETRIEVAL] ──► LLM direct answer (no DB)
          │
   [Standalone Query]
      ┌───┴───┐
      ▼       ▼
   Dense    Sparse (BM25)
      └───┬───┘
    EnsembleRetriever (60/40)
          │
    CohereRerank top-N
          │
    sort by chunk_id sequence
          │
    LLM final answer
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.config.rag_settings import rag_settings
from app.services.rag.generation.history_summarizer import compress_history
from app.services.rag.generation.llm_client import build_llm
from app.services.rag.generation.prompt_templates import DIRECT_SYSTEM, RAG_PROMPT
from app.services.rag.retrieval.dense_retriever import build_dense_retriever
from app.services.rag.retrieval.hybrid_fuser import build_hybrid_retriever
from app.services.rag.retrieval.query_rewriter import rewrite_query
from app.services.rag.retrieval.reranker import build_reranking_retriever
from app.services.rag.retrieval.sparse_retriever import build_sparse_retriever

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    answer: str
    sources: list[Document]
    query_id: str
    corpus_searched: str
    hyde_applied: bool = False
    sub_queries_generated: int = 1
    chunks_retrieved: int = 0
    chunks_after_rerank: int = 0
    latency_ms: int = 0


def _to_lc_messages(history: list[dict]) -> list[BaseMessage]:
    result = []
    for msg in history:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        result.append(cls(content=msg["content"]))
    return result


class RAGPipeline:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._embeddings = OpenAIEmbeddings(
            model=rag_settings.EMBEDDING_MODEL,
            openai_api_key=rag_settings.OPENROUTER_API_KEY,
            openai_api_base=rag_settings.OPENROUTER_BASE_URL,
            dimensions=rag_settings.EMBEDDING_DIMENSIONS,
        )
        self._qdrant = QdrantClient(
            url=rag_settings.QDRANT_URL,
            api_key=rag_settings.QDRANT_API_KEY,
            timeout=60,
        )
        self._llm = build_llm()

    async def query(
        self,
        question: str,
        namespace: str,
        doc_id: str | None = None,
        history: list[dict] | None = None,
    ) -> RAGResult:
        start = time.monotonic()
        query_id = str(uuid.uuid4())[:8]
        history = history or []

        # Compress history if it exceeds the token budget (summarise old turns)
        history = await compress_history(history, self._llm)

        lc_history = _to_lc_messages(history)

        logger.info(
            "RAG query | id=%s namespace=%s history_turns=%d", query_id, namespace, len(history)
        )

        # ── Step 1: Query rewriting (only when there is prior history) ────────
        if history:
            standalone = await rewrite_query(question, history, self._llm)
        else:
            standalone = question  # first message — nothing to resolve

        # ── Step 2: No-retrieval path (chitchat / thanks / unrelated) ─────────
        if standalone is None:
            logger.info("RAG query id=%s → NO_RETRIEVAL, answering from history", query_id)
            response = await self._llm.ainvoke(
                [DIRECT_SYSTEM] + lc_history + [HumanMessage(content=question)]
            )
            return RAGResult(
                answer=response.content,
                sources=[],
                query_id=query_id,
                corpus_searched=namespace,
                chunks_retrieved=0,
                chunks_after_rerank=0,
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        logger.info("RAG query id=%s → standalone: %s", query_id, standalone[:120])

        # ── Step 3: Retrieve ──────────────────────────────────────────────────
        dense = build_dense_retriever(self._qdrant, self._embeddings, namespace, doc_id)
        sparse = build_sparse_retriever(namespace)
        hybrid = build_hybrid_retriever(dense, sparse)
        retriever = build_reranking_retriever(hybrid, top_n=rag_settings.RAG_RERANK_TOP_N)

        sources: list[Document] = await retriever.ainvoke(standalone)

        # Sort by chunk sequence so split sentences stitch back in document order
        sources.sort(key=lambda d: d.metadata.get("chunk_id", ""))

        # ── Step 4: Generate ──────────────────────────────────────────────────
        answer = await create_stuff_documents_chain(self._llm, RAG_PROMPT).ainvoke(
            {"input": question, "context": sources, "history": lc_history}
        )

        latency = int((time.monotonic() - start) * 1000)
        logger.info(
            "RAG complete | id=%s latency=%dms chunks=%d",
            query_id,
            latency,
            len(sources),
        )

        return RAGResult(
            answer=answer,
            sources=sources,
            query_id=query_id,
            corpus_searched=namespace,
            chunks_retrieved=len(sources),
            chunks_after_rerank=len(sources),
            latency_ms=latency,
        )

    async def query_stream(
        self,
        question: str,
        namespace: str,
        doc_id: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Yield NDJSON events: meta → token* → done."""
        start = time.monotonic()
        query_id = str(uuid.uuid4())[:8]
        history = history or []

        history = await compress_history(history, self._llm)
        lc_history = _to_lc_messages(history)

        if history:
            standalone = await rewrite_query(question, history, self._llm)
        else:
            standalone = question

        # No-retrieval path (chitchat)
        if standalone is None:
            yield {"type": "meta", "sources": [], "query_id": query_id, "chunks_retrieved": 0}
            async for chunk in self._llm.astream(
                [DIRECT_SYSTEM] + lc_history + [HumanMessage(content=question)]
            ):
                token = chunk.content
                if token:
                    yield {"type": "token", "content": token}
            yield {"type": "done", "latency_ms": int((time.monotonic() - start) * 1000)}
            return

        # Retrieve
        dense = build_dense_retriever(self._qdrant, self._embeddings, namespace, doc_id)
        sparse = build_sparse_retriever(namespace)
        hybrid = build_hybrid_retriever(dense, sparse)
        retriever = build_reranking_retriever(hybrid, top_n=rag_settings.RAG_RERANK_TOP_N)
        sources: list[Document] = await retriever.ainvoke(standalone)
        sources.sort(key=lambda d: d.metadata.get("chunk_id", ""))

        source_dicts = [
            {
                "chunk_id": s.metadata.get("chunk_id", ""),
                "doc_id": s.metadata.get("doc_id"),
                "corpus_name": s.metadata.get("corpus_type", s.metadata.get("namespace", "")),
                "section_path": s.metadata.get("section_path"),
                "page_num": s.metadata.get("page_num") or s.metadata.get("page_number"),
                "relevance_score": float(s.metadata.get("relevance_score", 0.0)),
                "text_excerpt": s.page_content[:400],
            }
            for s in sources
        ]

        yield {
            "type": "meta",
            "sources": source_dicts,
            "query_id": query_id,
            "chunks_retrieved": len(sources),
        }

        # Format prompt and stream LLM tokens
        context_text = "\n\n".join(s.page_content for s in sources)
        messages = RAG_PROMPT.format_messages(
            input=question,
            context=context_text,
            history=lc_history,
        )
        async for chunk in self._llm.astream(messages):
            token = chunk.content
            if token:
                yield {"type": "token", "content": token}

        yield {"type": "done", "latency_ms": int((time.monotonic() - start) * 1000)}
