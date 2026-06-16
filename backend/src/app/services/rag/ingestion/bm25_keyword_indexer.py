import logging
import pickle
import re
from pathlib import Path

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.services.config.rag_settings import rag_settings

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "is", "it", "in", "of", "and", "or", "to", "for",
        "with", "on", "at", "by", "this", "that", "be", "are", "was", "were",
        "as", "from", "have", "has", "had", "not", "but", "if", "its", "do",
        "does", "did", "will", "would", "can", "could", "should", "may",
    }
)


class BM25Indexer:
    def __init__(self) -> None:
        self._dir = Path(rag_settings.BM25_INDEX_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def build(self, chunks: list[Document], namespace: str) -> None:
        tokenized = [self._tokenize(c.page_content) for c in chunks]
        chunk_ids = [c.metadata.get("chunk_id", str(i)) for i, c in enumerate(chunks)]
        doc_ids = [c.metadata.get("doc_id", "") for c in chunks]
        texts = [c.page_content for c in chunks]
        index = BM25Okapi(tokenized)
        index_path = self._dir / f"{namespace}.pkl"
        with open(index_path, "wb") as f:
            pickle.dump({"index": index, "chunk_ids": chunk_ids, "doc_ids": doc_ids, "texts": texts}, f)
        logger.info("BM25 index built | namespace=%s chunks=%d path=%s", namespace, len(chunks), index_path)

    def search(self, query: str, namespace: str, k: int = 20) -> list[tuple[str, float, str]]:
        """Returns list of (chunk_id, score, text)."""
        data = self._load(namespace)
        if not data:
            return []
        scores = data["index"].get_scores(self._tokenize(query))
        ranked = sorted(
            zip(data["chunk_ids"], scores, data["texts"]),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(cid, score, text) for cid, score, text in ranked[:k] if score > 0]

    def delete_by_doc_id(self, namespace: str, doc_id: str) -> None:
        data = self._load(namespace)
        if not data:
            return

        keep = [i for i, d in enumerate(data["doc_ids"]) if d != doc_id]
        if not keep:
            # All chunks belonged to this doc — remove the index file entirely.
            path = self._dir / f"{namespace}.pkl"
            path.unlink(missing_ok=True)
            logger.info("BM25 index removed (empty after delete) | namespace=%s doc_id=%s", namespace, doc_id)
            return

        filtered_chunks = [
            Document(page_content=data["texts"][i], metadata={"chunk_id": data["chunk_ids"][i], "doc_id": data["doc_ids"][i]})
            for i in keep
        ]
        self.build(filtered_chunks, namespace)
        logger.info("BM25 index rebuilt after delete | namespace=%s removed=%d remaining=%d", namespace, len(data["chunk_ids"]) - len(keep), len(keep))

    def _load(self, namespace: str) -> dict | None:
        path = self._dir / f"{namespace}.pkl"
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s\-\/\.]", "", text)
        return [t for t in text.split() if t not in _STOP_WORDS and len(t) > 1]
