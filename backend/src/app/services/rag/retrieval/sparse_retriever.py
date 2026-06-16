import pickle
from pathlib import Path

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from app.services.config.rag_settings import rag_settings


def build_sparse_retriever(namespace: str) -> BM25Retriever | None:
    path = Path(rag_settings.BM25_INDEX_DIR) / f"{namespace}.pkl"
    if not path.exists():
        return None

    with open(path, "rb") as f:
        data = pickle.load(f)

    doc_ids = data.get("doc_ids", [""] * len(data["chunk_ids"]))
    docs = [
        Document(
            page_content=text,
            metadata={"chunk_id": cid, "doc_id": did, "namespace": namespace},
        )
        for cid, did, text in zip(data["chunk_ids"], doc_ids, data["texts"])
        if text.strip()
    ]

    if not docs:
        return None

    retriever = BM25Retriever.from_documents(docs)
    retriever.k = rag_settings.RAG_SPARSE_K
    return retriever
