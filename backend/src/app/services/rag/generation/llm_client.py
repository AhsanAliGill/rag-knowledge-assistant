from langchain_groq import ChatGroq

from app.services.config.rag_settings import rag_settings


def build_llm() -> ChatGroq:
    return ChatGroq(
        model=rag_settings.LLM_MODEL,
        temperature=rag_settings.LLM_TEMPERATURE,
        max_tokens=rag_settings.LLM_MAX_TOKENS,
        groq_api_key=rag_settings.GROQ_API_KEY,
    )
