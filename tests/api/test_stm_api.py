"""Tests for STM API routes (backed by LangGraph checkpointer + session_registry)."""

from datetime import UTC
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def _agent_svc(messages=None, state_extra=None):
    """Build a mock AgentService whose agent has get_state / update_state."""
    svc = MagicMock()
    sv = {
        "messages": messages or [],
        "user_id": "u1",
        "agent_id": "yuri",
        **(state_extra or {}),
    }
    checkpoint = MagicMock()
    checkpoint.values = sv
    svc.agent.get_state = MagicMock(return_value=checkpoint)
    svc.agent.update_state = MagicMock()
    svc.agent.checkpointer = MagicMock()
    return svc


# ---------- GET /get-chat-history ----------


def test_get_chat_history_success(client):
    """Test successful chat history retrieval via checkpointer."""
    messages = [
        HumanMessage(content="Hello!"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "test_tool",
                    "args": {"test_arg": "arg1"},
                    "id": "tool_id_test_123",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="Tool result", tool_call_id="tool_id_test_123", name="test_tool"
        ),
    ]
    svc = _agent_svc(messages=messages)

    with patch("src.api.routes.stm.get_agent_service", return_value=svc):
        response = client.get(
            "/v1/stm/get-chat-history",
            params={
                "user_id": "user123",
                "agent_id": "agent456",
                "session_id": "session789",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session789"
    assert len(data["messages"]) == 3
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello!"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["tool_calls"] == [
        {
            "type": "function",
            "id": "tool_id_test_123",
            "function": {"name": "test_tool", "arguments": '{"test_arg": "arg1"}'},
        }
    ]
    assert data["messages"][2]["role"] == "tool"
    assert data["messages"][2]["name"] == "test_tool"
    assert data["messages"][2]["tool_call_id"] == "tool_id_test_123"
    assert data["messages"][2]["content"] == "Tool result"


# ---------- POST /add-chat-history ----------


def test_add_chat_history_success(client):
    """Test successful chat history addition via checkpointer update_state."""
    svc = _agent_svc()

    with patch("src.api.routes.stm.get_agent_service", return_value=svc):
        response = client.post(
            "/v1/stm/add-chat-history",
            json={
                "user_id": "user123",
                "agent_id": "agent456",
                "session_id": "session789",
                "messages": [
                    {"role": "user", "content": "Hello!"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == "session789"
    assert data["message_count"] == 2
    svc.agent.update_state.assert_called_once()


def test_add_chat_history_invalid_message_type(client):
    """Test adding chat history with invalid message type."""
    svc = _agent_svc()

    with patch("src.api.routes.stm.get_agent_service", return_value=svc):
        response = client.post(
            "/v1/stm/add-chat-history",
            json={
                "user_id": "user123",
                "agent_id": "agent456",
                "session_id": "session789",
                "messages": [
                    {"role": "invalid_role", "content": "What?"},
                ],
            },
        )

    assert response.status_code == 500
    assert "Unexpected message type" in response.json()["detail"]


def test_add_chat_history_empty_content(client):
    """Test adding chat history with empty content — Pydantic rejects empty string fields."""
    response = client.post(
        "/v1/stm/add-chat-history",
        json={
            "user_id": "",
            "agent_id": "agent456",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 422
    assert (
        "String should have at least 1 character" in response.json()["detail"][0]["msg"]
    )


def test_add_chat_history_service_not_initialized(client):
    """Test adding chat history when service is not initialized."""
    with patch("src.api.routes.stm.get_agent_service", return_value=None):
        response = client.post(
            "/v1/stm/add-chat-history",
            json={
                "user_id": "user123",
                "agent_id": "agent456",
                "session_id": "session789",
                "messages": [{"role": "user", "content": "Hello!"}],
            },
        )

    assert response.status_code == 503
    assert "Agent service not initialized" in response.json()["detail"]


# ---------- GET /sessions ----------


def test_list_sessions_success(client):
    """Test successful session listing via session_registry."""
    from datetime import datetime

    registry = MagicMock()
    registry.list_sessions.return_value = [
        {
            "thread_id": "session1",
            "user_id": "user123",
            "agent_id": "agent456",
            "created_at": datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 1, 13, 0, tzinfo=UTC),
        },
    ]

    with patch("src.api.routes.stm.get_session_registry", return_value=registry):
        response = client.get(
            "/v1/stm/sessions",
            params={"user_id": "user123", "agent_id": "agent456"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session1"


def test_list_sessions_registry_unavailable(client):
    """Test listing sessions when registry is not initialized."""
    with patch("src.api.routes.stm.get_session_registry", return_value=None):
        response = client.get(
            "/v1/stm/sessions",
            params={"user_id": "user123", "agent_id": "agent456"},
        )

    assert response.status_code == 503


# ---------- DELETE /sessions/{session_id} ----------


def test_delete_session_success(client):
    """Test successful session deletion."""
    svc = _agent_svc()
    registry = MagicMock()
    registry.delete.return_value = True

    with (
        patch("src.api.routes.stm.get_agent_service", return_value=svc),
        patch("src.api.routes.stm.get_session_registry", return_value=registry),
    ):
        response = client.delete(
            "/v1/stm/sessions/session123",
            params={"user_id": "user123", "agent_id": "agent456"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]


def test_delete_session_not_found(client):
    """Test deleting non-existent session."""
    svc = _agent_svc()
    registry = MagicMock()
    registry.delete.return_value = False

    with (
        patch("src.api.routes.stm.get_agent_service", return_value=svc),
        patch("src.api.routes.stm.get_session_registry", return_value=registry),
    ):
        response = client.delete(
            "/v1/stm/sessions/session123",
            params={"user_id": "user123", "agent_id": "agent456"},
        )

    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


# ---------- PATCH /sessions/{session_id}/metadata ----------


def test_update_session_metadata_success(client):
    """Test successful session metadata update."""
    svc = _agent_svc()

    with patch("src.api.routes.stm.get_agent_service", return_value=svc):
        response = client.patch(
            "/v1/stm/sessions/session123/metadata",
            json={
                "session_id": "session123",
                "metadata": {"user_id": "user123"},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated" in data["message"].lower()


# ---------- GET /{session_id}/messages ----------


def test_get_session_messages(client):
    """Test new GET /{session_id}/messages endpoint."""
    messages = [
        HumanMessage(content="Hello!"),
        AIMessage(content="Hi there!"),
    ]
    svc = _agent_svc(messages=messages)

    with patch("src.api.routes.stm.get_agent_service", return_value=svc):
        response = client.get("/v1/stm/session789/messages")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session789"
    assert len(data["messages"]) == 2


# ---------- Validation (422) ----------


def test_message_parsing_all_types(client):
    """Test parsing all message types (system, user, assistant, tool)."""
    svc = _agent_svc()

    with patch("src.api.routes.stm.get_agent_service", return_value=svc):
        response = client.post(
            "/v1/stm/add-chat-history",
            json={
                "user_id": "user123",
                "agent_id": "agent456",
                "session_id": "session789",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {
                        "role": "user",
                        "content": "What is the length of the word 'extraordinary'?",
                    },
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": "chatcmpl-tool-11d1a983d7e241d6b015c804a0fd412d",
                                "function": {
                                    "name": "get_word_length",
                                    "arguments": '{"word": "extraordinary"}',
                                },
                            }
                        ],
                        "content": "",
                    },
                    {
                        "role": "tool",
                        "name": "get_word_length",
                        "tool_call_id": "chatcmpl-tool-11d1a983d7e241d6b015c804a0fd412d",
                        "content": "13",
                    },
                    {
                        "role": "assistant",
                        "content": 'The word "extraordinary" has a length of 13 letters.',
                    },
                ],
            },
        )

    assert response.status_code == 201
    assert response.json()["message_count"] == 5
