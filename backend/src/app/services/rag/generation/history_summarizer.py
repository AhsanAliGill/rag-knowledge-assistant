"""
Conversation history compression.

When total history tokens exceed MAX_HISTORY_TOKENS:
  older messages  →  LLM summarizer  →  one summary message
  recent N msgs   →  kept verbatim

Result passed to pipeline: [summary_msg] + recent_msgs
This prevents the context window from filling up on long conversations.
"""

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# Trigger compression when history exceeds this many estimated tokens
MAX_HISTORY_TOKENS: int = 3_000

# Always keep the last N messages verbatim (= RECENT_KEEP/2 full exchanges)
RECENT_KEEP: int = 6

_SUMMARIZER_SYSTEM = """You are a conversation summarizer.
Summarize the conversation below into a single compact paragraph.
Preserve: all key facts, numbers, dates, document names, decisions, and entity names.
Write in third person. Be concise but complete. Do NOT add opinions or inferences."""


def _estimate_tokens(messages: list[dict]) -> int:
    """Rough estimate: 4 characters ≈ 1 token."""
    return sum(len(m["content"]) for m in messages) // 4


async def _summarize(old_messages: list[dict], llm: BaseChatModel) -> str:
    formatted = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in old_messages
    )
    response = await llm.ainvoke([
        SystemMessage(content=_SUMMARIZER_SYSTEM),
        HumanMessage(content=f"Conversation to summarize:\n\n{formatted}"),
    ])
    return response.content.strip()


async def compress_history(
    history: list[dict],
    llm: BaseChatModel,
) -> list[dict]:
    """
    Returns history as-is if within limits.
    Otherwise returns [summary_dict] + last RECENT_KEEP messages.
    """
    if not history:
        return history

    if _estimate_tokens(history) <= MAX_HISTORY_TOKENS:
        return history

    # Split into old (compress) and recent (keep verbatim)
    if len(history) <= RECENT_KEEP:
        return history  # not enough messages to split, keep all

    old = history[:-RECENT_KEEP]
    recent = history[-RECENT_KEEP:]

    logger.info(
        "History compression: %d msgs → summary + %d recent (tokens ~%d)",
        len(old), len(recent), _estimate_tokens(old),
    )

    summary_text = await _summarize(old, llm)
    summary_msg = {
        "role": "assistant",
        "content": f"[Earlier conversation summary]: {summary_text}",
    }
    return [summary_msg] + recent
