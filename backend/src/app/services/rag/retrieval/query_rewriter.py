from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

_SYSTEM = """You are a query reformulation assistant. Given a chat history and the user's latest message, do exactly ONE of the following:

1. Respond with the exact token [NO_RETRIEVAL] ONLY if the message is one of these:
   - Pure chitchat, greetings, thanks, acknowledgements ("ok", "got it", "thanks", "that makes sense", "great")
   - A question strictly about the conversation itself ("what did I ask", "what did we discuss", "summarise our chat", "what was my previous question", "what have we talked about", "recall our conversation")
   - A follow-up whose exact answer was already fully stated earlier in THIS conversation (e.g. asking to repeat, rephrase, or clarify something already answered)

2. Otherwise — including any question that introduces a new topic, entity, section, or fact not already discussed in this conversation — rewrite the user's message into a single self-contained question that can be understood without the chat history. Incorporate all necessary context (resolve pronouns like "it", "that", "they"; carry over document names, thresholds, roles, numbers).

When in doubt, choose option 2. Only output [NO_RETRIEVAL] when you are certain no new document lookup is needed.

Rules:
- Output ONLY the rewritten question OR the exact token [NO_RETRIEVAL]. Nothing else.
- Do NOT answer the question.
- Do NOT add any preamble or explanation."""

_NO_RETRIEVAL_TOKEN = "[NO_RETRIEVAL]"


async def rewrite_query(
    question: str,
    history: list[dict],
    llm: BaseChatModel,
) -> str | None:
    """
    Returns a standalone question string ready for retrieval,
    or None when no retrieval is needed (chitchat / follow-up without doc need).
    """
    messages: list = [SystemMessage(content=_SYSTEM)]

    for msg in history:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))

    messages.append(HumanMessage(content=question))

    response = await llm.ainvoke(messages)
    result = response.content.strip()

    if _NO_RETRIEVAL_TOKEN in result:
        return None

    return result
