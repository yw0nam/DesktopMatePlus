"""Tests for MCP tool loading in OpenAIChatAgent.

Covers:
- Agent initializes correctly with mcp_config=None (no MCP)
- Agent gracefully degrades when get_tools() raises
- Agent loads tools when get_tools() succeeds
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


class TestMCPToolLoading:
    async def test_initialize_async_no_mcp_config(self):
        """Agent initializes correctly when mcp_config is None — no tools loaded."""
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
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
        ):
            mock_create_agent.return_value = MagicMock()

            await agent.initialize_async()

        assert agent._mcp_tools == []

    async def test_initialize_async_get_tools_raises_graceful_degradation(self):
        """Agent continues without MCP tools when get_tools() raises."""
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
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
        ):
            mock_mcp_instance = MagicMock()
            mock_mcp_instance.get_tools = AsyncMock(
                side_effect=RuntimeError("Server failed to start")
            )
            mock_mcp_cls.return_value = mock_mcp_instance
            mock_create_agent.return_value = MagicMock()

            await agent.initialize_async()

        # Graceful degradation: no tools, agent still created
        assert agent._mcp_tools == []
        assert agent.agent is not None

    async def test_initialize_async_get_tools_succeeds(self):
        """Agent loads tools when get_tools() returns successfully."""
        agent = make_agent(
            mcp_config={"my-server": {"command": "some-cmd", "transport": "stdio"}}
        )
        fake_tool = MagicMock()
        fake_tool.name = "fake_tool"

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
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
        ):
            mock_mcp_instance = MagicMock()
            mock_mcp_instance.get_tools = AsyncMock(return_value=[fake_tool])
            mock_mcp_cls.return_value = mock_mcp_instance
            mock_create_agent.return_value = MagicMock()

            await agent.initialize_async()

        assert agent._mcp_tools == [fake_tool]
        assert agent.agent is not None
