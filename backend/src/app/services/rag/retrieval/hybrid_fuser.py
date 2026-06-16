import logging

from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.retrievers import BaseRetriever

from app.services.config.rag_settings import rag_settings

logger = logging.getLogger(__name__)


def build_hybrid_retriever(
    dense_retriever: BaseRetriever,
    sparse_retriever: BaseRetriever | None,
) -> BaseRetriever:
    if sparse_retriever is None:
        logger.debug("BM25 index not found — using dense retriever only")
        return dense_retriever

    logger.debug("Using EnsembleRetriever (%.0f%% dense + %.0f%% BM25)",
                 rag_settings.RAG_DENSE_WEIGHT * 100,
                 (1 - rag_settings.RAG_DENSE_WEIGHT) * 100)
    return EnsembleRetriever(
        retrievers=[dense_retriever, sparse_retriever],
        weights=[rag_settings.RAG_DENSE_WEIGHT, 1.0 - rag_settings.RAG_DENSE_WEIGHT],
    )
