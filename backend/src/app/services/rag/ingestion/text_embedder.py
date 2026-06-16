import asyncio
import logging

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.services.config.rag_settings import rag_settings

logger = logging.getLogger(__name__)

# Max concurrent embedding API calls — prevents rate-limit errors on large docs
_EMBED_CONCURRENCY = 5


class EmbeddingEngine:
    def __init__(self) -> None:
        self._model = OpenAIEmbeddings(
            model=rag_settings.EMBEDDING_MODEL,
            openai_api_key=rag_settings.OPENROUTER_API_KEY,
            openai_api_base=rag_settings.OPENROUTER_BASE_URL,
            dimensions=rag_settings.EMBEDDING_DIMENSIONS,
        )
        logger.debug("EmbeddingEngine initialized | model=%s", rag_settings.EMBEDDING_MODEL)

    async def embed_documents(
        self,
        chunks: list[Document],
        batch_size: int | None = None,
    ) -> list[list[float]]:
        batch_size = batch_size or rag_settings.EMBEDDING_BATCH_SIZE
        texts = [c.page_content for c in chunks]
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        total_batches = len(batches)

        logger.info(
            "Embedding %d texts in %d parallel batches (batch_size=%d)",
            len(texts), total_batches, batch_size,
        )

        semaphore = asyncio.Semaphore(_EMBED_CONCURRENCY)

        async def _embed_batch(batch: list[str]) -> list[list[float]]:
            async with semaphore:
                return await self._model.aembed_documents(batch)

        results = await asyncio.gather(*[_embed_batch(b) for b in batches])

        vectors = [v for batch_vectors in results for v in batch_vectors]
        logger.info("Embedding complete | total_vectors=%d", len(vectors))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        logger.debug("Embedding query (%d chars)", len(text))
        return await self._model.aembed_query(text)
