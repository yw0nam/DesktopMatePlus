"""Tests for AgentService base class cleanup_async method."""

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from src.services.agent_service.service import AgentService


class _ConcreteAgent(AgentService):
    """Minimal concrete subclass for testing base class behavior."""

    def initialize_model(self) -> BaseChatModel:
        from unittest.mock import MagicMock

        return MagicMock(spec=BaseChatModel)

    async def is_healthy(self) -> tuple[bool, str]:
        return True, ""

    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        context: dict | None = None,
        is_new_session: bool = False,
    ):
        return
        yield  # make it a generator

    async def invoke(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        context: dict | None = None,
        is_new_session: bool = False,
    ) -> dict:
        return {"content": "", "new_chats": []}


def test_base_class_has_cleanup_async() -> None:
    assert hasattr(AgentService, "cleanup_async")


@pytest.mark.asyncio
async def test_cleanup_async_no_op_on_concrete_subclass() -> None:
    agent = _ConcreteAgent()
    # Should complete without raising
    await agent.cleanup_async()
