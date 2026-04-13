"""Tests for DelegateTaskTool."""

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.services.agent_service.tools.delegate.delegate_task import DelegateTaskTool


def _runtime(reply_channel=None, session_id="test-session"):
    r = MagicMock()
    r.state = {"user_id": "u1", "agent_id": "yuri"}
    r.context = {"reply_channel": reply_channel}
    r.config = {"configurable": {"thread_id": session_id}}
    return r


async def test_arun_inserts_pending_task_to_db():
    tool = DelegateTaskTool()
    mock_repo = MagicMock()
    with (
        patch("httpx.AsyncClient") as cls,
        patch(
            "src.services.service_manager.get_pending_task_repo",
            return_value=mock_repo,
        ),
    ):
        cls.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(post=AsyncMock())
        )
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("do research", runtime=_runtime())

    assert isinstance(result, Command)
    assert "pending_tasks" not in result.update
    mock_repo.insert.assert_called_once()
    inserted_doc = mock_repo.insert.call_args[0][0]
    assert inserted_doc.status == "running"
    assert inserted_doc.reply_channel is None
    assert inserted_doc.session_id == "test-session"


async def test_arun_captures_reply_channel():
    tool = DelegateTaskTool()
    rc = {"provider": "slack", "channel_id": "C1"}
    mock_repo = MagicMock()
    with (
        patch("httpx.AsyncClient") as cls,
        patch(
            "src.services.service_manager.get_pending_task_repo",
            return_value=mock_repo,
        ),
    ):
        cls.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(post=AsyncMock())
        )
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime(reply_channel=rc))

    assert isinstance(result, Command)
    inserted_doc = mock_repo.insert.call_args[0][0]
    assert inserted_doc.reply_channel == rc


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
