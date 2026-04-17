"""Unit tests for HitLMiddleware (Phase 2 — category-based)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.websocket import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware


class TestHitLMiddlewareCategory:
    def _mw(
        self, category_map: dict[str, ToolCategory] | None = None
    ) -> HitLMiddleware:
        return HitLMiddleware(category_map=category_map or {})

    def test_get_category_returns_mapped(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        assert mw.get_category("read_file") == ToolCategory.READ_ONLY

    def test_get_category_unknown_is_dangerous(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        assert mw.get_category("ghost_tool") == ToolCategory.DANGEROUS

    def test_requires_approval_bypasses_read_only(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        assert mw.requires_approval("read_file") is False

    @pytest.mark.parametrize(
        "cat",
        [ToolCategory.STATE_MUTATING, ToolCategory.EXTERNAL, ToolCategory.DANGEROUS],
    )
    def test_requires_approval_true_for_non_bypass(self, cat: ToolCategory):
        mw = self._mw({"t": cat})
        assert mw.requires_approval("t") is True


class TestHitLMiddlewareInterrupt:
    def _mw(self, category_map: dict[str, ToolCategory]) -> HitLMiddleware:
        return HitLMiddleware(category_map=category_map)

    @pytest.mark.asyncio
    async def test_read_only_tool_calls_handler_without_interrupt(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        request = MagicMock()
        request.tool_call = {"name": "read_file", "args": {"path": "/tmp/x"}}
        handler = AsyncMock(return_value="contents")

        result = await mw.awrap_tool_call(request, handler)

        handler.assert_awaited_once_with(request)
        assert result == "contents"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "category",
        [ToolCategory.STATE_MUTATING, ToolCategory.EXTERNAL, ToolCategory.DANGEROUS],
    )
    async def test_non_bypass_category_interrupts_with_category_payload(
        self, category: ToolCategory
    ):
        mw = self._mw({"write_file": category})
        request = MagicMock()
        request.tool_call = {"name": "write_file", "args": {"path": "/tmp/x"}}
        handler = AsyncMock(return_value="ok")

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": True, "request_id": "r-1"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            call_payload = mock_interrupt.call_args[0][0]
            assert call_payload["tool_name"] == "write_file"
            assert call_payload["tool_args"] == {"path": "/tmp/x"}
            assert call_payload["category"] == category.value
            assert "request_id" in call_payload

        handler.assert_awaited_once_with(request)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unknown_tool_treated_as_dangerous(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        request = MagicMock()
        request.tool_call = {"name": "ghost_tool", "args": {}}
        handler = AsyncMock()

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": False, "request_id": "r-2"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            assert (
                mock_interrupt.call_args[0][0]["category"]
                == ToolCategory.DANGEROUS.value
            )

        handler.assert_not_awaited()
        assert "ghost_tool" in result.lower() or "거부" in result

    @pytest.mark.asyncio
    async def test_denied_returns_error_string_without_handler(self):
        mw = self._mw({"write_file": ToolCategory.STATE_MUTATING})
        request = MagicMock()
        request.tool_call = {"name": "write_file", "args": {}}
        handler = AsyncMock()

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": False, "request_id": "r-3"},
        ):
            result = await mw.awrap_tool_call(request, handler)

        handler.assert_not_awaited()
        assert isinstance(result, str)
