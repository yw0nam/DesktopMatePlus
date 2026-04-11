"""Tests for MCP client lifecycle in OpenAIChatAgent.

Covers:
- Agent initializes correctly with mcp_config=None (no MCP)
- Agent gracefully degrades when MCP server fails to start
- cleanup_async() is safe to call when no MCP client exists
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.services.agent_service.openai_chat_agent import OpenAIChatAgent


def make_agent(mcp_config: dict | None = None) -> OpenAIChatAgent:
    """Construct a minimal OpenAIChatAgent for testing."""
    with patch("src.services.agent_service.openai_chat_agent.ChatOpenAI"):
        agent = OpenAIChatAgent(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test-key",
            model_name="gpt-4o",
            mcp_config=mcp_config,
        )
    agent.agent = MagicMock()
    agent._personas = {}
    return agent


class TestMCPLifecycle:
    async def test_initialize_async_no_mcp_config(self):
        """Agent initializes correctly when mcp_config is None."""
        agent = make_agent(mcp_config=None)

        with (
            patch(
                "src.services.agent_service.openai_chat_agent._load_personas",
                return_value={},
            ),
            patch(
                "src.services.service_manager.get_mongo_client",
                return_value=None,
            ),
            patch(
                "src.services.service_manager.get_user_profile_service",
                return_value=None,
            ),
            patch(
                "src.services.agent_service.tools.registry.ToolRegistry"
            ) as mock_registry,
            patch(
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
        ):
            mock_registry.return_value.get_enabled_tools.return_value = []
            mock_create_agent.return_value = MagicMock()

            await agent.initialize_async()

        assert agent._mcp_client is None
        assert agent._mcp_tools == []

    async def test_initialize_async_mcp_server_failure_graceful_degradation(self):
        """Agent continues without MCP tools when MCP server fails to start."""
        agent = make_agent(
            mcp_config={"bad-server": {"command": "nonexistent", "transport": "stdio"}}
        )

        with (
            patch(
                "src.services.agent_service.openai_chat_agent._load_personas",
                return_value={},
            ),
            patch(
                "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
            ) as mock_mcp_cls,
            patch(
                "src.services.service_manager.get_mongo_client",
                return_value=None,
            ),
            patch(
                "src.services.service_manager.get_user_profile_service",
                return_value=None,
            ),
            patch(
                "src.services.agent_service.tools.registry.ToolRegistry"
            ) as mock_registry,
            patch(
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
        ):
            mock_mcp_instance = MagicMock()
            mock_mcp_instance.__aenter__ = AsyncMock(
                side_effect=RuntimeError("Server failed to start")
            )
            mock_mcp_cls.return_value = mock_mcp_instance
            mock_registry.return_value.get_enabled_tools.return_value = []
            mock_create_agent.return_value = MagicMock()

            await agent.initialize_async()

        # Graceful degradation: no client, no tools, agent still created
        assert agent._mcp_client is None
        assert agent._mcp_tools == []
        assert agent.agent is not None

    async def test_cleanup_async_no_mcp_client_is_safe(self):
        """cleanup_async() must not raise when no MCP client exists."""
        agent = make_agent(mcp_config=None)
        assert agent._mcp_client is None

        # Must not raise
        await agent.cleanup_async()

        assert agent._mcp_client is None

    async def test_cleanup_async_closes_running_client(self):
        """cleanup_async() calls __aexit__ and clears the client reference."""
        agent = make_agent(mcp_config=None)

        mock_client = MagicMock()
        mock_client.__aexit__ = AsyncMock(return_value=None)
        agent._mcp_client = mock_client

        await agent.cleanup_async()

        mock_client.__aexit__.assert_awaited_once_with(None, None, None)
        assert agent._mcp_client is None

    async def test_cleanup_async_called_twice_is_safe(self):
        """Calling cleanup_async() twice must not raise."""
        agent = make_agent(mcp_config=None)

        mock_client = MagicMock()
        mock_client.__aexit__ = AsyncMock(return_value=None)
        agent._mcp_client = mock_client

        await agent.cleanup_async()
        await agent.cleanup_async()  # second call: _mcp_client is None, must be safe

        assert agent._mcp_client is None
