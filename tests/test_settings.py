"""Tests for settings configuration validator."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.configs.settings import (
    Settings,
    WebSocketConfig,
    initialize_settings,
    load_settings_from_yaml,
)


def test_websocket_config_defaults():
    """Test WebSocketConfig with default values."""
    config = WebSocketConfig()

    assert config.max_error_tolerance == 5
    assert config.error_backoff_seconds == 0.5
    assert config.inactivity_timeout_seconds == 300


def test_websocket_config_custom_values():
    """Test WebSocketConfig with custom values."""
    config = WebSocketConfig(
        max_error_tolerance=10,
        error_backoff_seconds=1.0,
        inactivity_timeout_seconds=600,
    )

    assert config.max_error_tolerance == 10
    assert config.error_backoff_seconds == 1.0
    assert config.inactivity_timeout_seconds == 600


def test_settings_defaults():
    """Test Settings with default values."""
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.cors_origins == ["*"]
    assert settings.app_name == "DesktopMate+ Backend"
    assert settings.app_version == "0.1.0"
    assert settings.debug is False
    assert settings.health_check_timeout == 5
    assert isinstance(settings.websocket, WebSocketConfig)


def test_settings_custom_values():
    """Test Settings with custom values."""
    settings = Settings(
        host="0.0.0.0",
        port=9000,
        cors_origins=["http://localhost:3000"],
        app_name="Test App",
        app_version="1.0.0",
        debug=True,
        health_check_timeout=10,
        websocket=WebSocketConfig(max_error_tolerance=20),
    )

    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.app_name == "Test App"
    assert settings.app_version == "1.0.0"
    assert settings.debug is True
    assert settings.health_check_timeout == 10
    assert settings.websocket.max_error_tolerance == 20


def test_load_settings_from_yaml():
    """Test loading settings from YAML file."""
    # Create a temporary YAML file
    config = {
        "settings": {
            "host": "0.0.0.0",
            "port": 9000,
            "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
            "app_name": "Test Backend",
            "app_version": "2.0.0",
            "debug": True,
            "health_check_timeout": 15,
            "websocket": {
                "max_error_tolerance": 10,
                "error_backoff_seconds": 1.5,
                "inactivity_timeout_seconds": 600,
            },
        }
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False
    ) as temp_file:
        yaml.dump(config, temp_file)
        temp_path = Path(temp_file.name)

    try:
        settings = load_settings_from_yaml(temp_path)

        assert settings.host == "0.0.0.0"
        assert settings.port == 9000
        assert settings.cors_origins == [
            "http://localhost:3000",
            "http://localhost:8080",
        ]
        assert settings.app_name == "Test Backend"
        assert settings.app_version == "2.0.0"
        assert settings.debug is True
        assert settings.health_check_timeout == 15
        assert settings.websocket.max_error_tolerance == 10
        assert settings.websocket.error_backoff_seconds == 1.5
        assert settings.websocket.inactivity_timeout_seconds == 600

    finally:
        temp_path.unlink()


def test_load_settings_from_yaml_with_defaults():
    """Test loading settings from YAML with partial config (using defaults)."""
    config = {
        "settings": {
            "host": "0.0.0.0",
            "port": 9000,
        }
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False
    ) as temp_file:
        yaml.dump(config, temp_file)
        temp_path = Path(temp_file.name)

    try:
        settings = load_settings_from_yaml(temp_path)

        # Custom values
        assert settings.host == "0.0.0.0"
        assert settings.port == 9000

        # Default values
        assert settings.cors_origins == ["*"]
        assert settings.app_name == "DesktopMate+ Backend"
        assert settings.debug is False
        assert settings.websocket.max_error_tolerance == 5

    finally:
        temp_path.unlink()


def test_load_settings_file_not_found():
    """Test loading settings from non-existent YAML file."""
    with pytest.raises(FileNotFoundError):
        load_settings_from_yaml("nonexistent.yml")


def test_initialize_settings():
    """Test initialize_settings function."""
    config = {
        "settings": {
            "host": "localhost",
            "port": 8080,
            "app_name": "Initialized App",
        }
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False
    ) as temp_file:
        yaml.dump(config, temp_file)
        temp_path = Path(temp_file.name)

    try:
        settings = initialize_settings(temp_path)

        assert settings.host == "localhost"
        assert settings.port == 8080
        assert settings.app_name == "Initialized App"

    finally:
        temp_path.unlink()


def test_settings_validation():
    """Test that invalid settings raise validation errors."""
    from pydantic import ValidationError

    # Invalid port (out of range)
    with pytest.raises(ValidationError):
        Settings(port=70000)

    with pytest.raises(ValidationError):
        Settings(port=0)

    # Invalid type for host
    with pytest.raises(ValidationError):
        Settings(host=123)

    # Invalid type for cors_origins
    with pytest.raises(ValidationError):
        Settings(cors_origins="not a list")

    # Invalid WebSocket config
    with pytest.raises(ValidationError):
        Settings(websocket={"max_error_tolerance": 0})  # Below minimum (ge=1)
