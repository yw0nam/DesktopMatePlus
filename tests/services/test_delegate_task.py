"""Tests for DelegateTaskTool."""

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.services.agent_service.tools.delegate.delegate_task import DelegateTaskTool


def _runtime(pending=None, reply_channel=None):
    r = MagicMock()
    r.state = {"pending_tasks": pending or []}
    r.context = {"reply_channel": reply_channel}
    return r


async def test_arun_creates_pending_task():
    tool = DelegateTaskTool()
    with patch("httpx.AsyncClient") as cls:
        cls.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(post=AsyncMock())
        )
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("do research", runtime=_runtime())

    assert isinstance(result, Command)
    assert len(result.update["pending_tasks"]) == 1
    assert result.update["pending_tasks"][0]["status"] == "running"
    assert result.update["pending_tasks"][0]["reply_channel"] is None


async def test_arun_captures_reply_channel():
    tool = DelegateTaskTool()
    rc = {"provider": "slack", "channel_id": "C1"}
    with patch("httpx.AsyncClient") as cls:
        cls.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(post=AsyncMock())
        )
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime(reply_channel=rc))

    assert result.update["pending_tasks"][0]["reply_channel"] == rc


async def test_arun_includes_tool_message():
    tool = DelegateTaskTool()
    with patch("httpx.AsyncClient") as cls:
        cls.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(post=AsyncMock())
        )
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime())

    assert isinstance(result.update["messages"][0], ToolMessage)


async def test_arun_http_failure_returns_command():
    tool = DelegateTaskTool()
    with patch("httpx.AsyncClient") as cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime())

    assert isinstance(result, Command)
    assert "통신에 실패" in result.update["messages"][0].content
