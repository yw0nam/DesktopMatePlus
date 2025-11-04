"""
Tests for Agent factory and service functionality.

Tests the Agent service integration with factory pattern.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage

from src.configs.agent import OpenAIChatAgentConfig
from src.services.agent_service.agent_factory import AgentFactory
from src.services.agent_service.openai_chat_agent import OpenAIChatAgent
from src.services.agent_service.service import AgentService


class TestAgentFactory:
    """Test Agent factory functionality."""

    def test_get_openai_chat_agent(self):
        """Test creating OpenAI Chat Agent via factory."""

        configs = OpenAIChatAgentConfig(
            openai_api_key="test_key",
            openai_api_base="http://localhost:5580/v1",
            model_name="test_model",
            temperature=0.7,
            top_p=0.9,
            mcp_config={},
        )
        agent_service = AgentFactory.get_agent_service(
            "openai_chat_agent", **configs.model_dump()
        )
        assert isinstance(agent_service, OpenAIChatAgent)
        assert isinstance(agent_service, AgentService)

    def test_get_unknown_service_type(self):
        """Test factory raises error for unknown service type."""
        with pytest.raises(ValueError, match="Unknown Agent service type"):
            AgentFactory.get_agent_service("unknown_service")

    def test_factory_with_all_params(self):
        """Test factory with all configuration parameters."""

        # Mock environment variable for API key
        with patch.dict(os.environ, {"LLM_API_KEY": "key123"}):

            configs = OpenAIChatAgentConfig(
                openai_api_base="http://localhost:5580/v1",
                model_name="test_model",
                temperature=0.7,
                top_p=0.9,
                mcp_config={},
            )
            agent_service = AgentFactory.get_agent_service(
                "openai_chat_agent", **configs.model_dump()
            )
        assert isinstance(agent_service, OpenAIChatAgent)
        assert agent_service.openai_api_key == "key123"
        assert agent_service.openai_api_base == "http://localhost:5580/v1"
        assert agent_service.model_name == "test_model"
        assert agent_service.temperature == 0.7
        assert agent_service.top_p == 0.9
        assert agent_service.mcp_config == {}

    def test_factory_with_default_params(self):
        """Test factory uses default parameters when not provided."""
        configs = OpenAIChatAgentConfig(
            openai_api_key="test_key",
            openai_api_base="http://localhost:5580/v1",
            model_name="test_model",
            mcp_config={},
        )
        agent_service = AgentFactory.get_agent_service(
            "openai_chat_agent", **configs.model_dump()
        )
        assert agent_service.temperature == 0.7
        assert agent_service.top_p == 0.9


class TestOpenAIChatAgent:
    """Test OpenAI Chat Agent service."""

    @pytest.fixture
    def agent_service(self):
        """Create an agent service instance for testing."""
        configs = OpenAIChatAgentConfig(
            openai_api_key="test_key",
            openai_api_base="http://localhost:5580/v1",
            model_name="test_model",
            temperature=0.7,
            top_p=0.9,
            mcp_config={},
        )
        return AgentFactory.get_agent_service(
            "openai_chat_agent",
            **configs.model_dump(),
        )

    def test_agent_initialization(self, agent_service):
        """Test agent service initializes correctly."""
        assert agent_service is not None
        assert agent_service.llm is not None
        assert agent_service.checkpoint is not None

    @pytest.mark.asyncio
    async def test_health_check_no_mcp(self, agent_service):
        """Test health check without MCP configuration."""

        # Mock the stream method to return a simple response
        async def mock_stream(*args, **kwargs):
            yield {
                "type": "stream_start",
                "data": {"turn_id": "test", "client_id": "test"},
            }

        agent_service.stream = mock_stream

        is_healthy, msg = await agent_service.is_healthy()
        assert is_healthy is True
        assert msg == "Agent is healthy."

    @pytest.mark.asyncio
    async def test_health_check_failure(self, agent_service):
        """Test health check handles failures gracefully."""

        # Mock the stream method to raise an exception
        async def mock_stream(*args, **kwargs):
            raise Exception("Test error")
            yield  # This line makes it a generator

        agent_service.stream = mock_stream

        is_healthy, msg = await agent_service.is_healthy()
        assert is_healthy is False
        assert "Health check failed" in msg
        assert "Test error" in msg

    @pytest.mark.asyncio
    async def test_stream_basic_functionality(self, agent_service):
        """Test basic streaming functionality."""
        # Mock MCP client to avoid external dependencies
        with patch(
            "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
        ) as mock_mcp:
            # Setup mock MCP client
            mock_client_instance = AsyncMock()
            mock_client_instance.get_tools = AsyncMock(return_value=[])
            mock_mcp.return_value = mock_client_instance

            # Mock the agent's astream method
            async def mock_astream(*args, **kwargs):
                yield (
                    AIMessageChunk(content="Hello"),
                    {"langgraph_node": "agent"},
                )

            with patch("langgraph.prebuilt.create_react_agent") as mock_create_agent:
                mock_agent = Mock()
                mock_agent.astream = mock_astream
                mock_create_agent.return_value = mock_agent

                messages = [HumanMessage(content="Hello")]
                results = []

                # Create mock services
                mock_stm_service = Mock()
                mock_stm_service.add_chat_history.return_value = "session_123"
                mock_ltm_service = Mock()
                mock_ltm_service.add_memory.return_value = "memory_456"

                async for result in agent_service.stream(
                    messages=messages,
                    client_id="test_client",
                    stm_service=mock_stm_service,
                    ltm_service=mock_ltm_service,
                ):
                    results.append(result)

                # Check that we got some results
                assert len(results) > 0
                # Check for stream_start event
                assert any(r.get("type") == "stream_start" for r in results)

    @pytest.mark.asyncio
    async def test_stream_with_mcp_tools(self):
        """Test streaming with MCP tools configured."""
        mcp_config = {
            "test-server": {
                "command": "test",
                "args": ["test"],
                "transport": "stdio",
            }
        }
        configs = OpenAIChatAgentConfig(
            openai_api_key="test_key",
            openai_api_base="http://localhost:5580/v1",
            model_name="test_model",
            temperature=0.7,
            top_p=0.9,
            mcp_config=mcp_config,
        )
        agent_service = AgentFactory.get_agent_service(
            "openai_chat_agent", **configs.model_dump()
        )

        with patch(
            "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
        ) as mock_mcp:
            # Setup mock MCP client without tools to avoid tool validation issues
            mock_client_instance = AsyncMock()
            mock_client_instance.get_tools = AsyncMock(return_value=[])
            mock_mcp.return_value = mock_client_instance

            async def mock_astream(*args, **kwargs):
                yield (
                    AIMessageChunk(content="Response"),
                    {"langgraph_node": "agent"},
                )

            with patch("langgraph.prebuilt.create_react_agent") as mock_create_agent:
                mock_agent = Mock()
                mock_agent.astream = mock_astream
                mock_create_agent.return_value = mock_agent

                messages = [HumanMessage(content="Test")]
                results = []

                # Create mock services
                mock_stm_service = Mock()
                mock_stm_service.add_chat_history.return_value = "session_123"
                mock_ltm_service = Mock()
                mock_ltm_service.add_memory.return_value = "memory_456"

                async for result in agent_service.stream(
                    messages=messages,
                    client_id="test_client",
                    stm_service=mock_stm_service,
                    ltm_service=mock_ltm_service,
                ):
                    results.append(result)

                # Verify MCP client was initialized with config
                mock_mcp.assert_called_once_with(mcp_config)
                # Verify tools were fetched
                mock_client_instance.get_tools.assert_called_once()

    def test_initialize_model(self, agent_service):
        """Test model initialization."""
        llm, checkpoint = agent_service.initialize_model()

        assert llm is not None
        assert checkpoint is not None
        # Verify LLM has correct configuration
        assert llm.model_name == "test_model"
        assert llm.temperature == 0.7
        assert llm.openai_api_base == "http://localhost:5580/v1"
