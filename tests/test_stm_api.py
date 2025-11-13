"""Tests for STM API routes."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@pytest.fixture
def mock_stm_service():
    """Create a mock STM service."""
    with patch("src.api.routes.stm.get_stm_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


def test_add_chat_history_success(mock_stm_service, client):
    """Test successful chat history addition."""
    mock_stm_service.add_chat_history.return_value = "test_session_123"

    response = client.post(
        "/v1/stm/chat-history",
        json={
            "user_id": "user123",
            "agent_id": "agent456",
            "session_id": None,
            "messages": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == "test_session_123"
    assert data["message_count"] == 2


def test_add_chat_history_invalid_message_type(mock_stm_service, client):
    """Test adding chat history with invalid message type."""
    response = client.post(
        "/v1/stm/chat-history",
        json={
            "user_id": "user123",
            "agent_id": "agent456",
            "messages": [
                {
                    "role": "invalid_role",
                    "content": "What is the length of the word 'extraordinary'?",
                },
            ],
        },
    )

    assert response.status_code == 400
    assert "Unexpected message type" in response.json()["detail"]


def test_add_chat_history_empty_content(mock_stm_service, client):
    """Test adding chat history with empty content."""
    response = client.post(
        "/v1/stm/chat-history",
        json={
            "user_id": "user123",
            "agent_id": "agent456",
            "messages": [{"role": "user", "content": ""}],
        },
    )

    assert response.status_code == 400
    assert "Input should be a valid string" in response.json()["detail"]


def test_add_chat_history_service_not_initialized(client):
    """Test adding chat history when service is not initialized."""
    with patch("src.api.routes.stm.get_stm_service", return_value=None):
        response = client.post(
            "/v1/stm/chat-history",
            json={
                "user_id": "user123",
                "agent_id": "agent456",
                "messages": [
                    {
                        "role": "user",
                        "content": "What is the length of the word 'extraordinary'?",
                    }
                ],
            },
        )

    assert response.status_code == 503
    assert "STM service not initialized" in response.json()["detail"]


def test_get_chat_history_success(mock_stm_service, client):
    """Test successful chat history retrieval."""
    mock_stm_service.get_chat_history.return_value = [
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

    response = client.get(
        "/v1/stm/chat-history",
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


def test_get_chat_history_with_limit(mock_stm_service, client):
    """Test chat history retrieval with limit."""
    mock_stm_service.get_chat_history.return_value = [
        HumanMessage(content="Hello!"),
    ]

    response = client.get(
        "/v1/stm/chat-history",
        params={
            "user_id": "user123",
            "agent_id": "agent456",
            "session_id": "session789",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    mock_stm_service.get_chat_history.assert_called_once_with(
        user_id="user123",
        agent_id="agent456",
        session_id="session789",
        limit=10,
    )


def test_list_sessions_success(mock_stm_service, client):
    """Test successful session listing."""
    from datetime import datetime, timezone

    mock_stm_service.list_sessions.return_value = [
        {
            "session_id": "session1",
            "user_id": "user123",
            "agent_id": "agent456",
            "created_at": datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc),
            "metadata": {"title": "Test Session"},
        },
    ]

    response = client.get(
        "/v1/stm/sessions",
        params={
            "user_id": "user123",
            "agent_id": "agent456",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session1"
    assert data["sessions"][0]["metadata"]["title"] == "Test Session"


def test_delete_session_success(mock_stm_service, client):
    """Test successful session deletion."""
    mock_stm_service.delete_session.return_value = True

    response = client.delete(
        "/v1/stm/sessions/session123",
        params={
            "user_id": "user123",
            "agent_id": "agent456",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]


def test_delete_session_not_found(mock_stm_service, client):
    """Test deleting non-existent session."""
    mock_stm_service.delete_session.return_value = False

    response = client.delete(
        "/v1/stm/sessions/session123",
        params={
            "user_id": "user123",
            "agent_id": "agent456",
        },
    )

    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_update_session_metadata_success(mock_stm_service, client):
    """Test successful session metadata update."""
    mock_stm_service.update_session_metadata.return_value = True

    response = client.patch(
        "/v1/stm/sessions/session123/metadata",
        json={
            "session_id": "session123",
            "metadata": {"title": "Updated Title", "tags": ["important"]},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated successfully" in data["message"]


def test_update_session_metadata_not_found(mock_stm_service, client):
    """Test updating metadata for non-existent session."""
    mock_stm_service.update_session_metadata.return_value = False

    response = client.patch(
        "/v1/stm/sessions/session123/metadata",
        json={
            "session_id": "session123",
            "metadata": {"title": "Updated Title"},
        },
    )

    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_message_parsing_all_types(mock_stm_service, client):
    """Test parsing all message types (system, user, assistant, tool)."""
    mock_stm_service.add_chat_history.return_value = "session_xyz"

    response = client.post(
        "/v1/stm/chat-history",
        json={
            "user_id": "user123",
            "agent_id": "agent456",
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
