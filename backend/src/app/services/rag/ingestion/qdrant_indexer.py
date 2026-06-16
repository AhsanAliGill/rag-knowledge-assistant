import asyncio
import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PayloadSchemaType, PointStruct, VectorParams

from app.services.config.rag_settings import rag_settings

logger = logging.getLogger(__name__)


def _chunk_uuid(chunk_id: str) -> str:
    """Deterministic UUID from chunk_id so re-uploads overwrite instead of duplicate."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class VectorIndexer:
    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            url=rag_settings.QDRANT_URL,
            api_key=rag_settings.QDRANT_API_KEY,
            prefer_grpc=False,
            timeout=120,
        )

    async def ensure_collection(self) -> None:
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if rag_settings.QDRANT_COLLECTION not in names:
            await self._client.create_collection(
                collection_name=rag_settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=rag_settings.EMBEDDING_DIMENSIONS,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", rag_settings.QDRANT_COLLECTION)
        else:
            logger.debug("Qdrant collection already exists: %s", rag_settings.QDRANT_COLLECTION)

        # Create indexes for both nested (new format) and flat (old format) fields.
        # create_payload_index is idempotent — safe to call on existing indexes.
        for field in ("metadata.namespace", "metadata.doc_id", "namespace", "doc_id"):
            await self._client.create_payload_index(
                collection_name=rag_settings.QDRANT_COLLECTION,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.debug("Ensured payload index: %s", field)

    async def upsert(
        self,
        chunk_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        points = []
        for chunk_id, vector, payload in zip(chunk_ids, vectors, payloads):
            # Store in langchain_qdrant-compatible format so QdrantVectorStore
            # returns full metadata (doc_id, page_num, etc.) on retrieval.
            text = payload.pop("text", "")
            points.append(PointStruct(
                id=_chunk_uuid(chunk_id),
                vector=vector,
                payload={
                    "page_content": text,
                    "metadata": payload,   # all remaining fields nested here
                },
            ))

        batch_size = 50
        batches = [points[i : i + batch_size] for i in range(0, len(points), batch_size)]
        semaphore = asyncio.Semaphore(10)

        async def _upsert_batch(batch: list[PointStruct]) -> None:
            async with semaphore:
                await self._client.upsert(
                    collection_name=rag_settings.QDRANT_COLLECTION,
                    points=batch,
                )

        await asyncio.gather(*[_upsert_batch(b) for b in batches])
        logger.info("Upserted %d vectors to Qdrant in %d parallel batches", len(points), len(batches))

    async def delete_by_doc_id(self, doc_id: str) -> None:
        # Ensure indexes exist before filtering (idempotent, safe to call here).
        await self.ensure_collection()

        # Delete new-format points (nested metadata.doc_id).
        await self._client.delete(
            collection_name=rag_settings.QDRANT_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))]
            ),
        )

        # Delete old-format points (flat doc_id) for backward compatibility.
        await self._client.delete(
            collection_name=rag_settings.QDRANT_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )

        logger.info("Deleted vectors for doc_id=%s from Qdrant", doc_id)
