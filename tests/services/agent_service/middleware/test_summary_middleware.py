"""Tests for summary_middleware hooks."""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.conversation_summary import ConversationSummary


def _make_summary(
    session_id: str = "u:a", text: str = "Prior summary."
) -> ConversationSummary:
    from datetime import datetime

    return ConversationSummary(
        session_id=session_id,
        summary_text=text,
        turn_range_start=0,
        turn_range_end=20,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def state_with_system():
    return {
        "user_id": "u",
        "agent_id": "a",
        "messages": [
            SystemMessage(id="sys-001", content="You are Yuri."),
            HumanMessage(content="Hi"),
        ],
    }


class TestSummaryInjectHook:
    async def test_injects_summary_into_system_message(self, state_with_system):
        mock_svc = MagicMock()
        mock_svc.get_summaries.return_value = [_make_summary()]

        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            result = await summary_inject_hook(state_with_system, runtime=None)

        assert result is not None
        msg = result["messages"][0]
        assert isinstance(msg, SystemMessage)
        assert "Prior summary." in msg.content
        assert msg.id == "sys-001"
        assert "You are Yuri." in msg.content

    async def test_returns_none_when_no_service(self, state_with_system):
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=None,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            result = await summary_inject_hook(state_with_system, runtime=None)
        assert result is None

    async def test_returns_none_when_no_user_id(self):
        mock_svc = MagicMock()
        state = {"user_id": "", "agent_id": "a", "messages": []}
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            result = await summary_inject_hook(state, runtime=None)
        assert result is None

    async def test_returns_none_when_no_summaries(self, state_with_system):
        mock_svc = MagicMock()
        mock_svc.get_summaries.return_value = []
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            result = await summary_inject_hook(state_with_system, runtime=None)
        assert result is None

    async def test_returns_none_when_no_system_message_with_id(self):
        mock_svc = MagicMock()
        mock_svc.get_summaries.return_value = [_make_summary()]
        state = {
            "user_id": "u",
            "agent_id": "a",
            "messages": [HumanMessage(content="Hi")],
        }
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            result = await summary_inject_hook(state, runtime=None)
        assert result is None

    async def test_uses_session_id_from_user_and_agent(self, state_with_system):
        mock_svc = MagicMock()
        mock_svc.get_summaries.return_value = []
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            await summary_inject_hook(state_with_system, runtime=None)

        mock_svc.get_summaries.assert_called_once_with("u:a")

    async def test_replaces_multi_paragraph_existing_summary(self):
        mock_svc = MagicMock()
        mock_svc.get_summaries.return_value = [_make_summary(text="New summary text.")]
        state = {
            "user_id": "u",
            "agent_id": "a",
            "messages": [
                SystemMessage(
                    id="sys-001",
                    content="You are Yuri.\n\nPrevious Conversation Summary: Old summary paragraph one.\n\nOld summary paragraph two with details.\n\nOld summary paragraph three.",
                ),
            ],
        }
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_inject_hook,
            )

            result = await summary_inject_hook(state, runtime=None)

        assert result is not None
        msg = result["messages"][0]
        assert "You are Yuri." in msg.content
        assert "New summary text." in msg.content
        assert "Old summary paragraph one" not in msg.content
        assert "Old summary paragraph two" not in msg.content


class TestSummaryConsolidationHook:
    def _make_state(self, n_human: int, last: int = 0) -> dict:
        messages = [HumanMessage(content=f"msg {i}") for i in range(n_human)]
        return {
            "user_id": "u",
            "agent_id": "a",
            "messages": messages,
            "summary_last_consolidated_at_turn": last,
        }

    def test_does_not_trigger_below_threshold(self):
        state = self._make_state(n_human=5, last=0)
        mock_svc = MagicMock()
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_consolidation_hook,
            )

            result = summary_consolidation_hook(state, runtime=None)
        assert result is None

    def test_triggers_at_threshold(self):
        state = self._make_state(n_human=20, last=0)
        mock_svc = MagicMock()
        with (
            patch(
                "src.services.agent_service.middleware.summary_middleware.get_summary_service",
                return_value=mock_svc,
            ),
            patch(
                "src.services.agent_service.middleware.summary_middleware.asyncio.create_task",
                side_effect=lambda coro: coro.close(),
            ) as mock_create_task,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_consolidation_hook,
            )

            result = summary_consolidation_hook(state, runtime=None)

        assert result == {"summary_last_consolidated_at_turn": 20}
        mock_create_task.assert_called_once()

    def test_returns_none_when_no_service(self):
        state = self._make_state(n_human=20, last=0)
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=None,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_consolidation_hook,
            )

            result = summary_consolidation_hook(state, runtime=None)
        assert result is None

    def test_does_not_trigger_when_already_consolidated(self):
        state = self._make_state(n_human=25, last=20)
        mock_svc = MagicMock()
        with patch(
            "src.services.agent_service.middleware.summary_middleware.get_summary_service",
            return_value=mock_svc,
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_consolidation_hook,
            )

            result = summary_consolidation_hook(state, runtime=None)
        assert result is None

    def test_updates_last_consolidated_turn(self):
        state = self._make_state(n_human=30, last=0)
        mock_svc = MagicMock()
        with (
            patch(
                "src.services.agent_service.middleware.summary_middleware.get_summary_service",
                return_value=mock_svc,
            ),
            patch(
                "src.services.agent_service.middleware.summary_middleware.asyncio.create_task",
                side_effect=lambda coro: coro.close(),
            ),
        ):
            from src.services.agent_service.middleware.summary_middleware import (
                summary_consolidation_hook,
            )

            result = summary_consolidation_hook(state, runtime=None)
        assert result["summary_last_consolidated_at_turn"] == 30
