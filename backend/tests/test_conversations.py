"""
Integration tests for conversation endpoints:
  GET  /api/v1/rag/conversations
  GET  /api/v1/rag/conversations/{id}
  DELETE /api/v1/rag/conversations/{id}

Conversations are seeded by making a POST /rag/query with a mocked pipeline.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.rag.pipeline import RAGResult

CONV_URL = "/api/v1/rag/conversations"
QUERY_URL = "/api/v1/rag/query"

_FAKE_RESULT = RAGResult(
    answer="Here is the answer.",
    sources=[],
    query_id="conv0001",
    corpus_searched="default_cdc",
    chunks_retrieved=0,
    chunks_after_rerank=0,
    latency_ms=50,
)


@pytest.fixture
def mock_pipeline():
    with patch("app.controllers.query_controller.RAGPipeline") as MockPipeline:
        instance = AsyncMock()
        instance.query = AsyncMock(return_value=_FAKE_RESULT)
        MockPipeline.return_value = instance
        yield instance


async def _new_conversation(
    client: AsyncClient, token: str, question: str = "What is the policy?"
) -> str:
    """Create a conversation by querying once; returns its UUID string."""
    r = await client.post(
        QUERY_URL,
        json={"question": question},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    return r.json()["conversation_id"]


# ── List ──────────────────────────────────────────────────────────────────────


async def test_list_conversations_empty(client: AsyncClient, auth_token: str):
    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token}"})
    assert r.status_code == 200
    assert r.json() == []


async def test_list_conversations_returns_created(
    client: AsyncClient, auth_token: str, mock_pipeline
):
    conv_id = await _new_conversation(client, auth_token)
    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token}"})
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert conv_id in ids


async def test_list_conversations_schema(client: AsyncClient, auth_token: str, mock_pipeline):
    await _new_conversation(client, auth_token)
    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token}"})
    item = r.json()[0]
    assert "id" in item
    assert "title" in item
    assert "created_at" in item
    assert "updated_at" in item


async def test_list_conversations_title_set_from_question(
    client: AsyncClient, auth_token: str, mock_pipeline
):
    await _new_conversation(client, auth_token, question="Tell me about vacation days")
    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token}"})
    assert r.json()[0]["title"] == "Tell me about vacation days"


async def test_list_conversations_user_isolation(
    client: AsyncClient, auth_token: str, auth_token2: str, mock_pipeline
):
    """User 1's conversations must not appear for User 2."""
    await _new_conversation(client, auth_token)
    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token2}"})
    assert r.json() == []


async def test_list_multiple_conversations(client: AsyncClient, auth_token: str, mock_pipeline):
    await _new_conversation(client, auth_token, "Question A")
    await _new_conversation(client, auth_token, "Question B")
    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token}"})
    assert len(r.json()) == 2


async def test_list_conversations_no_auth(client: AsyncClient):
    r = await client.get(CONV_URL)
    assert r.status_code == 401


# ── Get ───────────────────────────────────────────────────────────────────────


async def test_get_conversation_success(client: AsyncClient, auth_token: str, mock_pipeline):
    conv_id = await _new_conversation(client, auth_token)
    r = await client.get(f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == conv_id
    assert "messages" in data
    assert "title" in data


async def test_get_conversation_has_user_and_assistant_messages(
    client: AsyncClient, auth_token: str, mock_pipeline
):
    conv_id = await _new_conversation(client, auth_token)
    r = await client.get(f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"})
    roles = [m["role"] for m in r.json()["messages"]]
    assert "user" in roles
    assert "assistant" in roles


async def test_get_conversation_messages_in_chronological_order(
    client: AsyncClient, auth_token: str, mock_pipeline
):
    r1 = await client.post(
        QUERY_URL,
        json={"question": "First question"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    conv_id = r1.json()["conversation_id"]

    await client.post(
        QUERY_URL,
        json={"question": "Second question", "conversation_id": conv_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    r = await client.get(f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"})
    messages = r.json()["messages"]
    # 4 messages: user1, assistant1, user2, assistant2
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "First question"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Second question"


async def test_get_conversation_message_schema(client: AsyncClient, auth_token: str, mock_pipeline):
    conv_id = await _new_conversation(client, auth_token)
    r = await client.get(f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"})
    msg = r.json()["messages"][0]
    assert "id" in msg
    assert "role" in msg
    assert "content" in msg
    assert "created_at" in msg


async def test_get_conversation_not_found(client: AsyncClient, auth_token: str):
    r = await client.get(
        f"{CONV_URL}/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 404


async def test_get_conversation_wrong_user(
    client: AsyncClient, auth_token: str, auth_token2: str, mock_pipeline
):
    conv_id = await _new_conversation(client, auth_token)
    r = await client.get(
        f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token2}"}
    )
    assert r.status_code == 404


async def test_get_conversation_no_auth(client: AsyncClient):
    r = await client.get(f"{CONV_URL}/{uuid.uuid4()}")
    assert r.status_code == 401


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_delete_conversation_success(client: AsyncClient, auth_token: str, mock_pipeline):
    conv_id = await _new_conversation(client, auth_token)

    r = await client.delete(
        f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert r.status_code == 204

    # Confirm it's gone
    get_r = await client.get(
        f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert get_r.status_code == 404


async def test_delete_removes_from_list(client: AsyncClient, auth_token: str, mock_pipeline):
    conv_id = await _new_conversation(client, auth_token)
    await client.delete(f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"})

    r = await client.get(CONV_URL, headers={"Authorization": f"Bearer {auth_token}"})
    assert r.json() == []


async def test_delete_conversation_not_found(client: AsyncClient, auth_token: str):
    r = await client.delete(
        f"{CONV_URL}/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 404


async def test_delete_conversation_wrong_user(
    client: AsyncClient, auth_token: str, auth_token2: str, mock_pipeline
):
    conv_id = await _new_conversation(client, auth_token)

    r = await client.delete(
        f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token2}"}
    )
    assert r.status_code == 404

    # Original still accessible to owner
    get_r = await client.get(
        f"{CONV_URL}/{conv_id}", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert get_r.status_code == 200


async def test_delete_conversation_no_auth(client: AsyncClient):
    r = await client.delete(f"{CONV_URL}/{uuid.uuid4()}")
    assert r.status_code == 401


async def test_delete_only_own_conversation_not_others(
    client: AsyncClient, auth_token: str, mock_pipeline
):
    """Deleting one conversation must not affect other conversations of the same user."""
    conv_a = await _new_conversation(client, auth_token, "Question A")
    conv_b = await _new_conversation(client, auth_token, "Question B")

    await client.delete(f"{CONV_URL}/{conv_a}", headers={"Authorization": f"Bearer {auth_token}"})

    # conv_b still accessible
    r = await client.get(f"{CONV_URL}/{conv_b}", headers={"Authorization": f"Bearer {auth_token}"})
    assert r.status_code == 200
