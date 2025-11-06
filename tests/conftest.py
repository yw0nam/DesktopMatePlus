"""Test configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_user_id():
    """Return a sample user ID for testing."""
    return "test_user_123"


@pytest.fixture
def sample_thread_id():
    """Return a sample thread ID for testing."""
    return "test_thread_456"


@pytest.fixture(scope="session")
def test_settings_yaml():
    """Create a temporary YAML settings file for testing."""
    config = {
        "services": {
            "vlm_service": "openai_compatible.yml",
            "tts_service": "fish_speech.yml",
            "agent_service": "openai_chat_agent.yml",
            "stm_service": "mongodb.yml",
            "ltm_service": "mem0.yml",
        },
        "settings": {
            "host": "127.0.0.1",
            "port": 8000,
            "cors_origins": ["*"],
            "app_name": "DesktopMate+ Backend Test",
            "app_version": "0.1.0-test",
            "debug": True,
            "health_check_timeout": 5,
            "websocket": {
                "max_error_tolerance": 5,
                "error_backoff_seconds": 0.5,
                "inactivity_timeout_seconds": 300,
            },
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False
    ) as temp_file:
        yaml.dump(config, temp_file)
        temp_path = Path(temp_file.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


@pytest.fixture(scope="function")
def initialize_test_settings(test_settings_yaml):
    """Initialize settings from test YAML file."""
    from src.configs.settings import initialize_settings

    settings = initialize_settings(test_settings_yaml)
    return settings
