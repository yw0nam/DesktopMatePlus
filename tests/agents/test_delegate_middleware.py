"""Tests for DelegateToolMiddleware."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.agent_service.utils.delegate_middleware import DelegateToolMiddleware


class TestDelegateToolMiddleware:
    def test_instantiation(self):
        mw = DelegateToolMiddleware()
        assert isinstance(mw, DelegateToolMiddleware)

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_stm_passes_through(self):
        """Without stm_service, calls handler directly."""
        mw = DelegateToolMiddleware()
        mock_request = Mock()
        mock_handler = AsyncMock(return_value="result")
        with patch(
            "src.services.service_manager.get_stm_service",
            return_value=None,
        ):
            result = await mw.awrap_model_call(mock_request, mock_handler)
        mock_handler.assert_called_once_with(mock_request)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_awrap_tool_call_non_delegate_passes_through(self):
        """Non-delegate tool calls pass through unchanged."""
        mw = DelegateToolMiddleware()
        mock_request = Mock()
        mock_request.tool_call = {"name": "some_other_tool"}
        mock_handler = AsyncMock(return_value="tool_result")
        with patch(
            "src.services.agent_service.utils.delegate_middleware.get_config"
        ) as mock_cfg:
            mock_cfg.return_value = {"configurable": {"session_id": "sess-123"}}
            result = await mw.awrap_tool_call(mock_request, mock_handler)
        mock_handler.assert_called_once_with(mock_request)
        assert result == "tool_result"
