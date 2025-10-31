"""Test MongoDB configuration in STM settings."""

from src.configs.stm import MongoDBShortTermMemory, STMConfig


def test_mongodb_stm_defaults():
    """Test that MongoDB STM settings have correct default values."""
    config = STMConfig()

    # Test connection string
    assert config.mongodb.connection_string == "mongodb://admin:test@localhost:27017/"

    # Test database name
    assert config.mongodb.database_name == "desktopmate_db"

    # Test collection names
    assert config.mongodb.sessions_collection_name == "sessions"
    assert config.mongodb.messages_collection_name == "messages"


def test_mongodb_stm_can_be_overridden():
    """Test that MongoDB STM settings can be overridden."""
    # Override settings with custom values
    config = STMConfig(
        mongodb=MongoDBShortTermMemory(
            connection_string="mongodb://test:test@localhost:27018/",
            database_name="test_db",
            sessions_collection_name="test_sessions",
            messages_collection_name="test_messages",
        )
    )

    # Verify overrides
    assert config.mongodb.connection_string == "mongodb://test:test@localhost:27018/"
    assert config.mongodb.database_name == "test_db"
    assert config.mongodb.sessions_collection_name == "test_sessions"
    assert config.mongodb.messages_collection_name == "test_messages"


def test_stm_config_instantiation():
    """Test that STM config can be instantiated without errors."""
    config = STMConfig()
    assert config is not None
    assert config.mongodb is not None
    assert hasattr(config.mongodb, "connection_string")
    assert hasattr(config.mongodb, "database_name")
    assert hasattr(config.mongodb, "sessions_collection_name")
    assert hasattr(config.mongodb, "messages_collection_name")
