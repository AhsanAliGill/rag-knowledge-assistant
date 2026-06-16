import os

from dotenv import load_dotenv

load_dotenv()


class RAGSettings:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")

    # LLM served via ChatGroq (free tier)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

    # Embeddings via OpenRouter endpoint (OpenAI-compatible API, OpenRouter key only)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-large")
    EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

    COHERE_RERANK_MODEL: str = os.getenv("COHERE_RERANK_MODEL", "rerank-english-v3.0")

    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "rag_documents")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    PARENT_CHUNK_SIZE: int = int(os.getenv("PARENT_CHUNK_SIZE", "2000"))
    CHILD_CHUNK_SIZE: int = int(os.getenv("CHILD_CHUNK_SIZE", "500"))  # tokens
    CHILD_CHUNK_OVERLAP: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "100"))  # tokens = 20%
    MAX_CHILD_TOKENS: int = int(os.getenv("MAX_CHILD_TOKENS", "512"))

    RAG_DENSE_K: int = int(os.getenv("RAG_DENSE_K", "20"))
    RAG_SPARSE_K: int = int(os.getenv("RAG_SPARSE_K", "20"))
    RAG_DENSE_WEIGHT: float = float(os.getenv("RAG_DENSE_WEIGHT", "0.6"))
    RAG_RERANK_TOP_N: int = int(os.getenv("RAG_RERANK_TOP_N", "8"))
    RAG_RELEVANCE_THRESHOLD: float = float(os.getenv("RAG_RELEVANCE_THRESHOLD", "0.25"))
    RAG_CONTEXT_TOKEN_BUDGET: int = int(os.getenv("RAG_CONTEXT_TOKEN_BUDGET", "3500"))

    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "500"))
    MAX_UPLOADS_PER_DAY: int = int(os.getenv("MAX_UPLOADS_PER_DAY", "10"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    BM25_INDEX_DIR: str = os.getenv("BM25_INDEX_DIR", "bm25_indexes")
    GROUND_TRUTH_DIR: str = os.getenv("GROUND_TRUTH_DIR", "ground_truth")

    CDC_TABLE_PAGES: list[int] = [33, 61]
    DEFAULT_CORPUS_NAMESPACE: str = "default_cdc"

    EVAL_FAITHFULNESS_THRESHOLD: float = 0.85
    EVAL_RELEVANCY_THRESHOLD: float = 0.80
    EVAL_PRECISION_THRESHOLD: float = 0.70
    EVAL_RECALL_THRESHOLD: float = 0.75


rag_settings = RAGSettings()
