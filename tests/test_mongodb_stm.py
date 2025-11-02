"""Test MongoDBSTM initialization and connection."""

from unittest.mock import MagicMock, patch

import pymongo
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)

from src.services.stm_service.mongodb import MongoDBSTM


def test_mongodb_stm_initialization():
    """Test that MongoDBSTM can be initialized with configuration."""
    connection_string = "mongodb://admin:test@localhost:27017/"
    database_name = "test_db"
    sessions_collection_name = "test_sessions"
    messages_collection_name = "test_messages"

    with patch("pymongo.MongoClient") as mock_client:
        # Mock the database and collections
        mock_db = MagicMock()
        mock_client_instance = mock_client.return_value
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        # Create MongoDBSTM instance
        stm = MongoDBSTM(
            connection_string=connection_string,
            database_name=database_name,
            sessions_collection_name=sessions_collection_name,
            messages_collection_name=messages_collection_name,
        )

        # Verify initialization
        assert stm is not None
        assert stm.connection_string == connection_string
        assert stm.database_name == database_name
        assert stm.sessions_collection_name == sessions_collection_name
        assert stm.messages_collection_name == messages_collection_name


def test_mongodb_stm_initialize_memory():
    """Test that initialize_memory connects to MongoDB properly."""
    connection_string = "mongodb://admin:test@localhost:27017/"
    database_name = "test_db"
    sessions_collection_name = "test_sessions"
    messages_collection_name = "test_messages"

    with patch("pymongo.MongoClient") as mock_client:
        # Mock the database and collections
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db

        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string=connection_string,
            database_name=database_name,
            sessions_collection_name=sessions_collection_name,
            messages_collection_name=messages_collection_name,
        )

        # Verify the client was created with correct connection string
        mock_client.assert_called_once_with(connection_string)
        assert stm.memory_client is mock_client_instance


def test_mongodb_stm_with_config_defaults():
    """Test that MongoDBSTM can use configuration from STMConfig."""
    from src.configs.stm import STMConfig

    config = STMConfig()

    with patch("pymongo.MongoClient") as mock_client:
        # Mock the database and collections
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "sessions": mock_sessions_collection,
            "messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db

        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string=config.mongodb.connection_string,
            database_name=config.mongodb.database_name,
            sessions_collection_name=config.mongodb.sessions_collection_name,
            messages_collection_name=config.mongodb.messages_collection_name,
        )

        # Verify the client was created with default connection string
        mock_client.assert_called_once_with("mongodb://admin:test@localhost:27017/")
        assert stm.connection_string == config.mongodb.connection_string
        assert stm.database_name == config.mongodb.database_name


def test_mongodb_stm_health_check_healthy():
    """Test that health check returns True when connection is healthy."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_client_instance = mock_client.return_value
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        is_healthy, message = stm.is_healthy()

        assert is_healthy is True
        assert "healthy" in message.lower()


def test_mongodb_stm_health_check_unhealthy():
    """Test that health check returns False when connection is unhealthy."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_client_instance = mock_client.return_value
        mock_client_instance.__getitem__.return_value = mock_db
        # First call succeeds (initialization), second call fails (health check)
        mock_client_instance.admin.command.side_effect = [
            {"ok": 1.0},  # For initialization
            pymongo.errors.ConnectionFailure("Connection failed"),  # For health check
        ]

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        is_healthy, message = stm.is_healthy()

        assert is_healthy is False
        assert "unhealthy" in message.lower()


def test_mongodb_stm_health_check_not_initialized():
    """Test that health check returns False when client is not initialized."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_client_instance = mock_client.return_value
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )
        stm._client = None

        is_healthy, message = stm.is_healthy()

        assert is_healthy is False
        assert "not initialized" in message


def test_mongodb_stm_creates_indexes():
    """Test that MongoDBSTM creates indexes on initialization."""
    with patch("pymongo.MongoClient") as mock_client:
        # Mock the database and collections
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Verify indexes were created on sessions collection
        mock_sessions_collection.create_index.assert_called_once_with(
            [("user_id", pymongo.ASCENDING), ("agent_id", pymongo.ASCENDING)],
            background=True,
            name="user_agent_idx",
        )

        # Verify indexes were created on messages collection
        mock_messages_collection.create_index.assert_called_once_with(
            [("session_id", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)],
            background=True,
            name="session_created_idx",
        )


def test_mongodb_stm_handles_index_creation_failure():
    """Test that MongoDBSTM handles index creation failures gracefully."""
    with patch("pymongo.MongoClient") as mock_client:
        # Mock the database and collections
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Simulate index creation failure
        mock_sessions_collection.create_index.side_effect = Exception(
            "Index creation failed"
        )

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        # Should not raise exception even if index creation fails
        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Verify the STM was still created successfully
        assert stm is not None
        assert stm.memory_client is mock_client_instance


def test_message_serialization_deserialization():
    """Test that messages can be serialized and deserialized correctly using LangChain utilities."""
    # Create various message types
    original_messages = [
        SystemMessage(content="You are a helpful assistant"),
        HumanMessage(content="Hello, how are you?"),
        AIMessage(content="I'm doing well, thank you!"),
        HumanMessage(content="What's the weather like?"),
        AIMessage(content="I don't have access to real-time weather data."),
    ]

    # Serialize messages using LangChain utility
    serialized = messages_to_dict(original_messages)

    # Verify serialization produces a list of dicts
    assert isinstance(serialized, list)
    assert all(isinstance(msg, dict) for msg in serialized)
    assert len(serialized) == len(original_messages)

    # Deserialize messages using LangChain utility
    deserialized = messages_from_dict(serialized)

    # Verify deserialization produces BaseMessage objects
    assert isinstance(deserialized, list)
    assert len(deserialized) == len(original_messages)

    # Verify message types and content are preserved
    for original, restored in zip(original_messages, deserialized, strict=False):
        assert isinstance(restored, type(original))
        assert original.content == restored.content


def test_add_chat_history_creates_new_session():
    """Test that add_chat_history creates a new session when session_id is None."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Create test messages
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]

        # Add chat history without session_id
        session_id = stm.add_chat_history("user1", "agent1", None, messages)

        # Verify a session was created
        assert session_id is not None
        assert isinstance(session_id, str)

        # Verify insert_one was called for the session
        mock_sessions_collection.insert_one.assert_called_once()
        session_doc = mock_sessions_collection.insert_one.call_args[0][0]
        assert session_doc["session_id"] == session_id
        assert session_doc["user_id"] == "user1"
        assert session_doc["agent_id"] == "agent1"
        assert "created_at" in session_doc
        assert "updated_at" in session_doc

        # Verify messages were inserted
        mock_messages_collection.insert_many.assert_called_once()
        message_docs = mock_messages_collection.insert_many.call_args[0][0]
        assert len(message_docs) == 2
        assert all(doc["session_id"] == session_id for doc in message_docs)


def test_add_chat_history_adds_to_existing_session():
    """Test that add_chat_history adds messages to an existing session."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Create test messages
        messages = [
            HumanMessage(content="Another question"),
            AIMessage(content="Another answer"),
        ]

        existing_session_id = "existing-session-123"

        # Add chat history to existing session
        session_id = stm.add_chat_history(
            "user1", "agent1", existing_session_id, messages
        )

        # Verify the same session_id is returned
        assert session_id == existing_session_id

        # Verify update_one was called (not insert_one)
        mock_sessions_collection.insert_one.assert_not_called()
        mock_sessions_collection.update_one.assert_called_once()

        # Verify the update query
        update_call = mock_sessions_collection.update_one.call_args
        assert update_call[0][0]["session_id"] == existing_session_id
        assert update_call[0][0]["user_id"] == "user1"
        assert update_call[0][0]["agent_id"] == "agent1"

        # Verify messages were inserted
        mock_messages_collection.insert_many.assert_called_once()
        message_docs = mock_messages_collection.insert_many.call_args[0][0]
        assert len(message_docs) == 2
        assert all(doc["session_id"] == existing_session_id for doc in message_docs)


def test_add_chat_history_with_empty_messages():
    """Test that add_chat_history handles empty message list."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Add chat history with empty messages
        session_id = stm.add_chat_history("user1", "agent1", None, [])

        # Verify a session was still created
        assert session_id is not None
        mock_sessions_collection.insert_one.assert_called_once()

        # Verify no messages were inserted
        mock_messages_collection.insert_many.assert_not_called()


def test_get_chat_history_retrieves_messages():
    """Test that get_chat_history retrieves messages from MongoDB."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock message documents with proper LangChain message format
        mock_message_docs = [
            {
                "session_id": "test-session",
                "message_data": {
                    "type": "human",
                    "data": {"content": "Hello", "type": "human"},
                },
                "created_at": "2024-01-01T00:00:00",
                "sequence": 0,
            },
            {
                "session_id": "test-session",
                "message_data": {
                    "type": "ai",
                    "data": {"content": "Hi there!", "type": "ai"},
                },
                "created_at": "2024-01-01T00:00:01",
                "sequence": 1,
            },
        ]

        # Mock the find query
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__iter__.return_value = iter(mock_message_docs)
        mock_messages_collection.find.return_value = mock_cursor

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Get chat history
        messages = stm.get_chat_history("user1", "agent1", "test-session")

        # Verify find was called with correct query
        mock_messages_collection.find.assert_called_once_with(
            {"session_id": "test-session"}
        )

        # Verify sort was called
        mock_cursor.sort.assert_called_once()

        # Verify messages were returned
        assert isinstance(messages, list)
        assert len(messages) == 2


def test_get_chat_history_with_limit():
    """Test that get_chat_history respects the limit parameter."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock 5 message documents with proper LangChain format
        mock_message_docs = [
            {
                "session_id": "test-session",
                "message_data": {
                    "type": "human",
                    "data": {"content": f"Message {i}", "type": "human"},
                },
                "created_at": f"2024-01-01T00:00:0{i}",
                "sequence": i,
            }
            for i in range(2, 5)  # Only return the last 3 messages
        ]

        # Mock the find query
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__.return_value = iter(mock_message_docs)
        mock_messages_collection.find.return_value = mock_cursor
        mock_messages_collection.count_documents.return_value = 5

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Get chat history with limit of 3
        messages = stm.get_chat_history("user1", "agent1", "test-session", limit=3)

        # Verify skip was called to skip the first 2 messages (5 total - 3 limit = 2 to skip)
        mock_cursor.skip.assert_called_once_with(2)
        mock_cursor.limit.assert_called_once_with(3)

        # Verify we got 3 messages
        assert len(messages) == 3


def test_get_chat_history_empty_session():
    """Test that get_chat_history returns empty list for session with no messages."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock empty result
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__iter__.return_value = iter([])
        mock_messages_collection.find.return_value = mock_cursor

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Get chat history for empty session
        messages = stm.get_chat_history("user1", "agent1", "empty-session")

        # Verify empty list is returned
        assert messages == []


def test_list_sessions():
    """Test that list_sessions retrieves all sessions for a user and agent."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock session documents
        from datetime import datetime, timezone

        mock_session_docs = [
            {
                "session_id": "session-1",
                "user_id": "user1",
                "agent_id": "agent1",
                "created_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "metadata": {"title": "First conversation"},
            },
            {
                "session_id": "session-2",
                "user_id": "user1",
                "agent_id": "agent1",
                "created_at": datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
                "metadata": {},
            },
        ]

        # Mock the find query
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__iter__.return_value = iter(mock_session_docs)
        mock_sessions_collection.find.return_value = mock_cursor

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # List sessions
        sessions = stm.list_sessions("user1", "agent1")

        # Verify find was called with correct query
        mock_sessions_collection.find.assert_called_once_with(
            {"user_id": "user1", "agent_id": "agent1"}
        )

        # Verify sort was called
        mock_cursor.sort.assert_called_once()

        # Verify sessions were returned
        assert isinstance(sessions, list)
        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session-1"
        assert sessions[1]["session_id"] == "session-2"


def test_list_sessions_empty():
    """Test that list_sessions returns empty list when no sessions exist."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock empty result
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__iter__.return_value = iter([])
        mock_sessions_collection.find.return_value = mock_cursor

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # List sessions
        sessions = stm.list_sessions("user1", "agent1")

        # Verify empty list is returned
        assert sessions == []


def test_delete_session_success():
    """Test that delete_session successfully deletes a session and its messages."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock find_one to return a session
        mock_sessions_collection.find_one.return_value = {
            "session_id": "session-1",
            "user_id": "user1",
            "agent_id": "agent1",
        }

        # Mock delete operations
        mock_delete_messages_result = MagicMock()
        mock_delete_messages_result.deleted_count = 5
        mock_messages_collection.delete_many.return_value = mock_delete_messages_result

        mock_delete_session_result = MagicMock()
        mock_delete_session_result.deleted_count = 1
        mock_sessions_collection.delete_one.return_value = mock_delete_session_result

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Delete session
        result = stm.delete_session("session-1", "user1", "agent1")

        # Verify find_one was called to verify session
        mock_sessions_collection.find_one.assert_called_once()

        # Verify messages were deleted
        mock_messages_collection.delete_many.assert_called_once_with(
            {"session_id": "session-1"}
        )

        # Verify session was deleted
        mock_sessions_collection.delete_one.assert_called_once()

        # Verify success
        assert result is True


def test_delete_session_not_found():
    """Test that delete_session returns False when session doesn't exist."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock find_one to return None (session not found)
        mock_sessions_collection.find_one.return_value = None

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Delete non-existent session
        result = stm.delete_session("nonexistent", "user1", "agent1")

        # Verify find_one was called
        mock_sessions_collection.find_one.assert_called_once()

        # Verify delete operations were NOT called
        mock_messages_collection.delete_many.assert_not_called()
        mock_sessions_collection.delete_one.assert_not_called()

        # Verify failure
        assert result is False


def test_update_session_metadata_success():
    """Test that update_session_metadata successfully updates metadata."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock update_one result
        mock_update_result = MagicMock()
        mock_update_result.matched_count = 1
        mock_sessions_collection.update_one.return_value = mock_update_result

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Update metadata
        metadata = {"title": "Updated conversation", "tags": ["important", "work"]}
        result = stm.update_session_metadata("session-1", metadata)

        # Verify update_one was called with correct parameters
        mock_sessions_collection.update_one.assert_called_once()
        call_args = mock_sessions_collection.update_one.call_args

        # Check query
        assert call_args[0][0] == {"session_id": "session-1"}

        # Check update operation uses dot notation
        update_op = call_args[0][1]
        assert "$set" in update_op
        assert "metadata.title" in update_op["$set"]
        assert update_op["$set"]["metadata.title"] == "Updated conversation"
        assert "metadata.tags" in update_op["$set"]

        # Verify success
        assert result is True


def test_update_session_metadata_session_not_found():
    """Test that update_session_metadata returns False when session doesn't exist."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock update_one result with no match
        mock_update_result = MagicMock()
        mock_update_result.matched_count = 0
        mock_sessions_collection.update_one.return_value = mock_update_result

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Update metadata for non-existent session
        result = stm.update_session_metadata("nonexistent", {"title": "Test"})

        # Verify failure
        assert result is False


def test_update_session_metadata_merge():
    """Test that update_session_metadata merges metadata correctly."""
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_sessions_collection = MagicMock()
        mock_messages_collection = MagicMock()

        # Mock update_one result
        mock_update_result = MagicMock()
        mock_update_result.matched_count = 1
        mock_sessions_collection.update_one.return_value = mock_update_result

        mock_client_instance = mock_client.return_value
        mock_db.__getitem__.side_effect = lambda name: {
            "test_sessions": mock_sessions_collection,
            "test_messages": mock_messages_collection,
        }[name]
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.admin.command.return_value = {"ok": 1.0}

        stm = MongoDBSTM(
            connection_string="mongodb://admin:test@localhost:27017/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )

        # Update with new and overlapping keys
        new_metadata = {
            "title": "New Title",  # Overwrites old
            "description": "A new field",  # New field
        }
        result = stm.update_session_metadata("session-1", new_metadata)

        # Verify the update operation
        call_args = mock_sessions_collection.update_one.call_args
        update_op = call_args[0][1]["$set"]

        # Both fields should be set with dot notation
        assert "metadata.title" in update_op
        assert "metadata.description" in update_op
        assert update_op["metadata.title"] == "New Title"
        assert update_op["metadata.description"] == "A new field"

        # Verify success
        assert result is True
