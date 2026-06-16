from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.services.config.rag_settings import rag_settings


def build_dense_retriever(
    qdrant_client: QdrantClient,
    embeddings: OpenAIEmbeddings,
    namespace: str,
    doc_id: str | None = None,
) -> VectorStoreRetriever:
    filters = [FieldCondition(key="metadata.namespace", match=MatchValue(value=namespace))]
    if doc_id:
        filters.append(FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id)))

    vectorstore = QdrantVectorStore(
        client=qdrant_client,
        collection_name=rag_settings.QDRANT_COLLECTION,
        embedding=embeddings,
    )
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": rag_settings.RAG_DENSE_K,
            "filter": Filter(must=filters),
        },
    )
