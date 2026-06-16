from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_core.retrievers import BaseRetriever

from app.services.config.rag_settings import rag_settings


def build_reranking_retriever(
    base_retriever: BaseRetriever,
    top_n: int,
) -> ContextualCompressionRetriever:
    reranker = CohereRerank(
        cohere_api_key=rag_settings.COHERE_API_KEY,
        model=rag_settings.COHERE_RERANK_MODEL,
        top_n=top_n,
    )
    return ContextualCompressionRetriever(
        base_compressor=reranker,
        base_retriever=base_retriever,
    )
