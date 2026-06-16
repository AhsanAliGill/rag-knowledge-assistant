import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chunk import ChunkType, RAGChunk
from app.models.document import DocumentStatus, RAGDocument
from app.models.ingestion_job import JobStatus, RAGIngestionJob
from app.services.rag.ingestion.bm25_keyword_indexer import BM25Indexer
from app.services.rag.ingestion.document_chunker import HierarchicalChunker
from app.services.rag.ingestion.text_embedder import EmbeddingEngine
from app.services.rag.ingestion.chunk_tagger import MetadataTagger
from app.services.rag.ingestion.pdf_parser import DocumentParser
from app.services.rag.ingestion.qdrant_indexer import VectorIndexer

logger = logging.getLogger(__name__)


class IngestionJobManager:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._parser = DocumentParser()
        self._chunker = HierarchicalChunker()
        self._tagger = MetadataTagger()
        self._embedder = EmbeddingEngine()
        self._vector = VectorIndexer()
        self._bm25 = BM25Indexer()

    async def run(self, job_id: uuid.UUID) -> None:
        job = await self._session.get(RAGIngestionJob, job_id)
        doc = await self._session.get(RAGDocument, job.doc_id)

        logger.info("Ingestion started | job=%s doc=%s file=%s", job_id, doc.id, doc.filename)

        try:
            # ── 1. Parse ────────────────────────────────────────────────────────
            await self._update_job(job, JobStatus.PROCESSING, 5, "Parsing PDF...")
            raw_docs, page_count, _ = self._parser.parse(doc.storage_path, [])

            # ── 2. Chunk ────────────────────────────────────────────────────────
            await self._update_job(job, JobStatus.PROCESSING, 20, "Chunking document...")
            parents, children = self._chunker.chunk(raw_docs)
            logger.info("Chunking done | parents=%d children=%d", len(parents), len(children))

            namespace = "shared"

            # ── 3. Tag metadata ─────────────────────────────────────────────────
            await self._update_job(job, JobStatus.PROCESSING, 35, "Tagging metadata...")
            tagged_parents = self._tagger.tag(parents, doc.id, job.user_id, 0)
            parent_id_map = {
                p.metadata.get("chunk_id_key"): p.metadata["chunk_id"]
                for p in tagged_parents
            }
            tagged_children = self._tagger.tag(children, doc.id, job.user_id, len(parents))
            for child in tagged_children:
                old_pid = child.metadata.get("parent_id")
                if old_pid and old_pid in parent_id_map:
                    child.metadata["parent_id"] = parent_id_map[old_pid]

            # ── 4. Embed + BM25 in parallel ─────────────────────────────────────
            # BM25 only needs the text — no need to wait for embeddings.
            await self._update_job(
                job, JobStatus.PROCESSING, 50,
                f"Embedding {len(tagged_children)} chunks + building keyword index...",
            )
            await self._vector.ensure_collection()

            vectors, _ = await asyncio.gather(
                self._embedder.embed_documents(tagged_children),
                asyncio.to_thread(self._bm25.build, tagged_children, namespace),
            )
            logger.info("Embedding + BM25 complete | vectors=%d", len(vectors))

            # ── 5. Qdrant upsert + DB save in parallel ──────────────────────────
            await self._update_job(job, JobStatus.PROCESSING, 80, "Indexing + saving...")
            chunk_ids = [c.metadata["chunk_id"] for c in tagged_children]
            payloads = [{**c.metadata, "text": c.page_content} for c in tagged_children]

            await asyncio.gather(
                self._vector.upsert(chunk_ids, vectors, payloads),
                self._save_chunks(tagged_parents + tagged_children, doc.id, job.user_id),
            )
            logger.info("Vectors upserted + chunks saved | namespace=%s", namespace)

            # ── 6. Finalise ─────────────────────────────────────────────────────
            doc.page_count = page_count
            doc.chunk_count = len(tagged_parents) + len(tagged_children)
            doc.status = DocumentStatus.READY
            doc.ready_at = datetime.now(timezone.utc)
            self._session.add(doc)

            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.message = "Ingestion complete."
            job.completed_at = datetime.now(timezone.utc)
            self._session.add(job)
            await self._session.commit()

            logger.info(
                "Ingestion completed | job=%s doc=%s chunks=%d duration=%.1fs",
                job_id, doc.id, doc.chunk_count,
                (job.completed_at - job.started_at).total_seconds(),
            )

        except Exception as exc:
            logger.error("Ingestion failed | job=%s error=%s", job_id, exc, exc_info=True)
            await self._fail(job, doc, str(exc))
            raise

    async def _update_job(
        self, job: RAGIngestionJob, status: JobStatus, progress: int, message: str
    ) -> None:
        job.status = status
        job.progress = progress
        job.message = message
        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        self._session.add(job)
        await self._session.commit()
        logger.debug("Job progress: %d%% — %s", progress, message)

    async def _save_chunks(
        self,
        chunks: list,
        doc_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> None:
        db_chunks = []
        for chunk in chunks:
            m = chunk.metadata
            raw_type = m.get("chunk_type", "child")
            try:
                ctype = ChunkType(raw_type)
            except ValueError:
                ctype = ChunkType.CHILD

            db_chunks.append(RAGChunk(
                id=m["chunk_id"],
                doc_id=doc_id,
                user_id=user_id,
                chunk_type=ctype,
                parent_id=m.get("parent_id"),
                child_index=m.get("child_index"),
                text=chunk.page_content,
                section_path=m.get("section_path"),
                page_num=m.get("page"),
                vector_id=m["chunk_id"] if ctype != ChunkType.PARENT else None,
                token_count=len(chunk.page_content.split()),
            ))

        self._session.add_all(db_chunks)
        await self._session.commit()
        logger.debug("Saved %d chunks to database", len(db_chunks))

    async def _fail(
        self,
        job: RAGIngestionJob,
        doc: RAGDocument,
        error: str,
    ) -> None:
        doc.status = DocumentStatus.FAILED
        doc.error_message = error[:2000]
        self._session.add(doc)
        job.status = JobStatus.FAILED
        job.error_message = error[:2000]
        job.completed_at = datetime.now(timezone.utc)
        self._session.add(job)
        await self._session.commit()
