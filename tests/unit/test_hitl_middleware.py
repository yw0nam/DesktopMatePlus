"""Unit tests for HitLMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware


class TestHitLMiddleware:
    """Test HitL middleware tool classification and interrupt behavior."""

    def _make_middleware(
        self, mcp_tool_names: set[str] | None = None
    ) -> HitLMiddleware:
        """Create middleware with given MCP tool names."""
        return HitLMiddleware(mcp_tool_names=mcp_tool_names or set())

    def test_safe_tool_passes_through(self):
        """Built-in tools should pass through without interrupt."""
        mw = self._make_middleware(mcp_tool_names={"mcp_search"})
        assert not mw.is_dangerous("memory_search")
        assert not mw.is_dangerous("update_user_profile")
        assert not mw.is_dangerous("some_builtin_tool")

    def test_mcp_tool_is_dangerous(self):
        """MCP tools should be classified as dangerous."""
        mw = self._make_middleware(mcp_tool_names={"mcp_search", "mcp_write"})
        assert mw.is_dangerous("mcp_search")
        assert mw.is_dangerous("mcp_write")

    def test_delegate_tool_is_dangerous(self):
        """delegate_task tool should always be dangerous."""
        mw = self._make_middleware()
        assert mw.is_dangerous("delegate_task")

    def test_builtin_tool_is_safe(self):
        """Tools not in deny list should be safe."""
        mw = self._make_middleware(mcp_tool_names={"mcp_tool"})
        assert not mw.is_dangerous("terminal")
        assert not mw.is_dangerous("read_file")

    @pytest.mark.asyncio
    async def test_safe_tool_calls_handler(self):
        """Safe tools should call handler directly."""
        mw = self._make_middleware(mcp_tool_names={"mcp_tool"})
        request = MagicMock()
        request.tool_call = {"name": "safe_tool", "args": {"key": "value"}}
        handler = AsyncMock(return_value="tool result")

        result = await mw.awrap_tool_call(request, handler)

        handler.assert_awaited_once_with(request)
        assert result == "tool result"

    @pytest.mark.asyncio
    async def test_dangerous_tool_triggers_interrupt(self):
        """Dangerous tools should call interrupt()."""
        mw = self._make_middleware(mcp_tool_names={"mcp_search"})
        request = MagicMock()
        request.tool_call = {"name": "mcp_search", "args": {"query": "test"}}
        handler = AsyncMock(return_value="tool result")

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": True, "request_id": "test-123"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            mock_interrupt.assert_called_once()
            call_args = mock_interrupt.call_args[0][0]
            assert call_args["tool_name"] == "mcp_search"
            assert call_args["tool_args"] == {"query": "test"}
            assert "request_id" in call_args

        # After approval, handler should be called
        handler.assert_awaited_once_with(request)
        assert result == "tool result"

    @pytest.mark.asyncio
    async def test_deny_returns_error_string(self):
        """Denied tools should return error string without calling handler."""
        mw = self._make_middleware(mcp_tool_names={"mcp_search"})
        request = MagicMock()
        request.tool_call = {"name": "mcp_search", "args": {}}
        handler = AsyncMock()

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": False, "request_id": "test-456"},
        ):
            result = await mw.awrap_tool_call(request, handler)

        handler.assert_not_awaited()
        assert "denied" in result.lower() or "mcp_search" in result.lower()
