"""Tests for DelegateToolMiddleware."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.services.agent_service.tools.delegate.delegate_task import DelegateTaskTool
from src.services.agent_service.utils.delegate_middleware import DelegateToolMiddleware


class TestDelegateToolMiddleware:
    def test_instantiation(self):
        mw = DelegateToolMiddleware()
        assert isinstance(mw, DelegateToolMiddleware)

    @pytest.mark.asyncio
    async def test_awrap_tool_call_non_delegate_passes_through(self):
        """Non-delegate tool calls pass through unchanged."""
        mw = DelegateToolMiddleware()
        mock_request = Mock()
        mock_request.tool_call = {"name": "some_other_tool"}
        mock_handler = AsyncMock(return_value="tool_result")
        result = await mw.awrap_tool_call(mock_request, mock_handler)
        mock_handler.assert_called_once_with(mock_request)
        assert result == "tool_result"


async def test_awrap_model_call_injects_delegate_tool_without_args():
    """DelegateTaskTool must be constructed with zero arguments."""
    middleware = DelegateToolMiddleware()
    request = MagicMock()
    request.tools = []
    captured = {}

    def capture_override(**kwargs):
        captured.update(kwargs)
        return request

    request.override = capture_override
    await middleware.awrap_model_call(request, AsyncMock())
    injected_tools = captured.get("tools", [])
    assert any(isinstance(t, DelegateTaskTool) for t in injected_tools)


async def test_awrap_tool_call_routes_only_delegate_tool():
    """awrap_tool_call must pass through non-delegate tool calls unchanged."""
    middleware = DelegateToolMiddleware()
    handler = AsyncMock()

    non_delegate_request = MagicMock()
    non_delegate_request.tool_call = {"name": "some_other_tool"}
    await middleware.awrap_tool_call(non_delegate_request, handler)
    handler.assert_called_once_with(non_delegate_request)
