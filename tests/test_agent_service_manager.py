"""
Tests for Agent service initialization via service manager.

Tests the service manager's agent initialization functionality.
"""

import os
from unittest.mock import Mock, patch

import pytest

from src.services.service_manager import (
    get_agent_service,
    initialize_agent_service,
    initialize_services,
)


class TestAgentServiceInitialization:
    """Test agent service initialization through service manager."""

    @pytest.fixture(autouse=True)
    def reset_service_instance(self):
        """Reset the global service instance before each test."""
        import src.services.service_manager as sm

        sm._agent_service_instance = None
        yield
        sm._agent_service_instance = None

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_with_defaults(self, mock_load_yaml, mock_factory):
        """Test agent service initialization with default config path."""
        # Setup mocks
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                },
            },
            "mcp_config": None,
        }
        mock_agent = Mock()
        mock_factory.return_value = mock_agent

        # Initialize service
        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "test_key",
                "LLM_BASE_URL": "http://localhost:5580/v1",
                "LLM_MODEL_NAME": "test_model",
            },
        ):
            service = initialize_agent_service()

        # Verify service was created
        assert service is mock_agent
        mock_factory.assert_called_once()

        # Verify factory was called with correct parameters
        call_args = mock_factory.call_args
        assert call_args[0][0] == "openai_chat_agent"
        assert call_args[1]["openai_api_key"] == "test_key"
        assert call_args[1]["openai_api_base"] == "http://localhost:5580/v1"
        assert call_args[1]["model_name"] == "test_model"
        assert call_args[1]["temperature"] == 0.7
        assert call_args[1]["top_p"] == 0.9

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_with_mcp_config(
        self, mock_load_yaml, mock_factory
    ):
        """Test agent service initialization with MCP configuration."""
        mcp_config = {
            "sequential-thinking": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                "transport": "stdio",
            }
        }
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {
                    "temperature": 0.8,
                    "top_p": 0.95,
                },
            },
            "mcp_config": mcp_config,
        }
        mock_agent = Mock()
        mock_factory.return_value = mock_agent

        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "test_key",
                "LLM_BASE_URL": "http://localhost:5580/v1",
                "LLM_MODEL_NAME": "gpt-4",
            },
        ):
            initialize_agent_service()

        # Verify MCP config was passed
        call_args = mock_factory.call_args
        assert call_args[1]["mcp_config"] == mcp_config

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_singleton_pattern(
        self, mock_load_yaml, mock_factory
    ):
        """Test that agent service follows singleton pattern."""
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {},
            }
        }
        mock_agent = Mock()
        mock_factory.return_value = mock_agent

        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "key", "LLM_BASE_URL": "url", "LLM_MODEL_NAME": "model"},
        ):
            # First initialization
            service1 = initialize_agent_service()
            # Second initialization (should return cached instance)
            service2 = initialize_agent_service()

        # Should be the same instance
        assert service1 is service2
        # Factory should only be called once
        assert mock_factory.call_count == 1

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_force_reinit(self, mock_load_yaml, mock_factory):
        """Test force reinitialization of agent service."""
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {},
            }
        }
        mock_agent1 = Mock()
        mock_agent2 = Mock()
        mock_factory.side_effect = [mock_agent1, mock_agent2]

        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "key", "LLM_BASE_URL": "url", "LLM_MODEL_NAME": "model"},
        ):
            # First initialization
            service1 = initialize_agent_service()
            # Force reinitialization
            service2 = initialize_agent_service(force_reinit=True)

        # Should be different instances
        assert service1 is not service2
        # Factory should be called twice
        assert mock_factory.call_count == 2

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_custom_config_path(
        self, mock_load_yaml, mock_factory
    ):
        """Test initialization with custom config path."""
        custom_path = "/custom/path/config.yml"
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {},
            }
        }
        mock_agent = Mock()
        mock_factory.return_value = mock_agent

        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "key", "LLM_BASE_URL": "url", "LLM_MODEL_NAME": "model"},
        ):
            initialize_agent_service(config_path=custom_path)

        # Verify custom path was used
        mock_load_yaml.assert_called_once()
        assert str(mock_load_yaml.call_args[0][0]) == custom_path

    def test_get_agent_service_before_init(self):
        """Test getting agent service before initialization."""
        service = get_agent_service()
        assert service is None

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_get_agent_service_after_init(self, mock_load_yaml, mock_factory):
        """Test getting agent service after initialization."""
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {},
            }
        }
        mock_agent = Mock()
        mock_factory.return_value = mock_agent

        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "key", "LLM_BASE_URL": "url", "LLM_MODEL_NAME": "model"},
        ):
            initialized_service = initialize_agent_service()
            retrieved_service = get_agent_service()

        assert retrieved_service is initialized_service
        assert retrieved_service is mock_agent

    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_missing_config_file(self, mock_load_yaml):
        """Test initialization with missing config file."""
        mock_load_yaml.side_effect = FileNotFoundError("Config not found")

        with pytest.raises(FileNotFoundError):
            initialize_agent_service()

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_factory_error(self, mock_load_yaml, mock_factory):
        """Test initialization handles factory errors."""
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {},
            }
        }
        mock_factory.side_effect = Exception("Factory error")

        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "key", "LLM_BASE_URL": "url", "LLM_MODEL_NAME": "model"},
        ):
            with pytest.raises(Exception, match="Factory error"):
                initialize_agent_service()

    @patch("src.services.service_manager.AgentFactory.get_agent_service")
    @patch("src.services.service_manager._load_yaml_config")
    def test_initialize_agent_service_env_override(self, mock_load_yaml, mock_factory):
        """Test that environment variables override YAML config."""
        mock_load_yaml.return_value = {
            "llm_config": {
                "type": "openai_chat_agent",
                "configs": {
                    "openai_api_base": "http://yaml-config:8080/v1",
                    "model": "yaml-model",
                },
            }
        }
        mock_agent = Mock()
        mock_factory.return_value = mock_agent

        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "env_key",
                "LLM_BASE_URL": "http://env-config:9090/v1",
                "LLM_MODEL_NAME": "env-model",
            },
        ):
            initialize_agent_service()

        # Verify environment variables took precedence
        call_args = mock_factory.call_args
        assert call_args[1]["openai_api_base"] == "http://env-config:9090/v1"
        assert call_args[1]["model_name"] == "env-model"
        assert call_args[1]["openai_api_key"] == "env_key"


class TestInitializeAllServices:
    """Test initialization of all services including agent."""

    @pytest.fixture(autouse=True)
    def reset_service_instances(self):
        """Reset all global service instances before each test."""
        import src.services.service_manager as sm

        sm._tts_service_instance = None
        sm._vlm_service_instance = None
        sm._agent_service_instance = None
        yield
        sm._tts_service_instance = None
        sm._vlm_service_instance = None
        sm._agent_service_instance = None

    @patch("src.services.service_manager.initialize_tts_service")
    @patch("src.services.service_manager.initialize_vlm_service")
    @patch("src.services.service_manager.initialize_agent_service")
    def test_initialize_services_all_three(
        self, mock_init_agent, mock_init_vlm, mock_init_tts
    ):
        """Test initializing all three services."""
        mock_tts = Mock()
        mock_vlm = Mock()
        mock_agent = Mock()
        mock_init_tts.return_value = mock_tts
        mock_init_vlm.return_value = mock_vlm
        mock_init_agent.return_value = mock_agent

        tts, vlm, agent = initialize_services()

        assert tts is mock_tts
        assert vlm is mock_vlm
        assert agent is mock_agent
        mock_init_tts.assert_called_once()
        mock_init_vlm.assert_called_once()
        mock_init_agent.assert_called_once()

    @patch("src.services.service_manager.initialize_tts_service")
    @patch("src.services.service_manager.initialize_vlm_service")
    @patch("src.services.service_manager.initialize_agent_service")
    def test_initialize_services_with_custom_paths(
        self, mock_init_agent, mock_init_vlm, mock_init_tts
    ):
        """Test initializing services with custom config paths."""
        mock_tts = Mock()
        mock_vlm = Mock()
        mock_agent = Mock()
        mock_init_tts.return_value = mock_tts
        mock_init_vlm.return_value = mock_vlm
        mock_init_agent.return_value = mock_agent

        custom_tts_path = "/custom/tts.yml"
        custom_vlm_path = "/custom/vlm.yml"
        custom_agent_path = "/custom/agent.yml"

        tts, vlm, agent = initialize_services(
            tts_config_path=custom_tts_path,
            vlm_config_path=custom_vlm_path,
            agent_config_path=custom_agent_path,
        )

        mock_init_tts.assert_called_once_with(
            config_path=custom_tts_path, force_reinit=False
        )
        mock_init_vlm.assert_called_once_with(
            config_path=custom_vlm_path, force_reinit=False
        )
        mock_init_agent.assert_called_once_with(
            config_path=custom_agent_path, force_reinit=False
        )
