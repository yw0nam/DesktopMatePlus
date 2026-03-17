"""
Tests for Agent factory and service functionality.

Tests the Agent service integration with factory pattern.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import HumanMessage

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

    def test_factory_passes_stm_service_to_agent(self):
        """stm_service kwarg reaches OpenAIChatAgent without OpenAIChatAgentConfig rejecting it."""
        mock_stm = Mock()
        configs = OpenAIChatAgentConfig(
            openai_api_key="test_key",
            openai_api_base="http://localhost:5580/v1",
            model_name="test_model",
            mcp_config={},
        )
        agent_service = AgentFactory.get_agent_service(
            "openai_chat_agent", stm_service=mock_stm, **configs.model_dump()
        )
        assert agent_service.stm_service is mock_stm


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
        # agent is None until initialize_async() is called
        assert agent_service.agent is None

    @pytest.mark.asyncio
    async def test_health_check_no_mcp(self, agent_service):
        """Test health check without MCP configuration."""
        # Set agent to a non-None sentinel so is_healthy proceeds past the guard
        agent_service.agent = Mock()

        # Mock the stream method to return a simple response
        async def mock_stream(*args, **kwargs):
            yield {
                "type": "stream_start",
                "data": {"turn_id": "test", "session_id": "test"},
            }

        agent_service.stream = mock_stream

        is_healthy, msg = await agent_service.is_healthy()
        assert is_healthy is True
        assert msg == "Agent is healthy."

    @pytest.mark.asyncio
    async def test_health_check_failure(self, agent_service):
        """Test health check handles failures gracefully."""
        # Set agent to a non-None sentinel so is_healthy proceeds past the guard
        agent_service.agent = Mock()

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
        """Test basic streaming — agent must be initialized first."""
        from langchain_core.messages import AIMessage

        # Setup mock agent
        async def mock_astream(*args, **kwargs):
            # Yield updates mode entry for model node
            yield ("updates", {"model": {"messages": [AIMessage(content="Hello")]}})
            # Yield messages mode entry
            yield (
                "messages",
                (AIMessage(content="Hello"), {"langgraph_node": "model"}),
            )

        mock_agent = Mock()
        mock_agent.astream = mock_astream
        agent_service.agent = mock_agent

        # Load personas so stream can find "yuri" — patch _personas directly
        agent_service._personas = {"yuri": "You are Yuri."}

        messages = [HumanMessage(content="Hello")]
        results = []
        mock_stm = Mock()
        mock_ltm = Mock()

        async for result in agent_service.stream(
            messages=messages,
            session_id="test_session",
            persona_id="yuri",
            stm_service=mock_stm,
            ltm_service=mock_ltm,
        ):
            results.append(result)

        assert any(r.get("type") == "stream_start" for r in results)
        assert any(r.get("type") == "stream_end" for r in results)

    @pytest.mark.asyncio
    async def test_stream_with_mcp_tools(self):
        """Test initialize_async caches MCP tools and creates agent."""
        from src.configs.agent import OpenAIChatAgentConfig
        from src.services.agent_service.agent_factory import AgentFactory

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
        agent_svc = AgentFactory.get_agent_service(
            "openai_chat_agent", **configs.model_dump()
        )

        with patch(
            "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
        ) as mock_mcp:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get_tools = AsyncMock(return_value=[])
            mock_mcp.return_value = mock_client

            with patch(
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create:
                mock_create.return_value = Mock()
                await agent_svc.initialize_async()

            mock_client.get_tools.assert_called_once()
            mock_create.assert_called_once()
            assert agent_svc.agent is not None

    def test_initialize_model_returns_llm(self, agent_service):
        """initialize_model returns a single BaseChatModel."""
        llm = agent_service.initialize_model()
        assert llm is not None
        assert llm.model_name == "test_model"
        assert llm.temperature == 0.7
        assert llm.openai_api_base == "http://localhost:5580/v1"

    def test_agent_has_no_checkpoint(self, agent_service):
        """After migration, checkpoint is removed."""
        assert not hasattr(agent_service, "checkpoint")

    def test_initialize_model_returns_only_llm(self, agent_service):
        """initialize_model returns BaseChatModel, not tuple."""
        result = agent_service.initialize_model()
        # Not a tuple — single LLM
        assert not isinstance(result, tuple)
        assert result is not None

    @pytest.mark.asyncio
    async def test_initialize_async_exists(self, agent_service):
        """initialize_async is callable on AgentService."""
        # Without mcp_config or stm_service, this should be a no-op
        await agent_service.initialize_async()
