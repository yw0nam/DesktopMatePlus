from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.channel_service import process_message


def _make_deps(invoke_content="응답"):
    agent_service = MagicMock()
    agent_service.invoke = AsyncMock(
        return_value={
            "content": invoke_content,
            "new_chats": [AIMessage(invoke_content)],
        }
    )
    stm = MagicMock()
    stm.upsert_session = MagicMock(return_value=True)
    stm.update_session_metadata = MagicMock(return_value=True)
    ltm = MagicMock()
    return agent_service, stm, ltm


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_calls_agent_invoke_with_human_message_when_text_provided(self):
        agent, stm, ltm = _make_deps()
        mock_slack = AsyncMock()

        with (
            patch(
                "src.services.channel_service.load_context",
                new=AsyncMock(return_value=[]),
            ),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch(
                "src.services.channel_service.get_slack_service",
                return_value=mock_slack,
            ),
        ):
            await process_message(
                text="안녕",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        call_messages = agent.invoke.call_args[1]["messages"]
        assert any(
            isinstance(m, HumanMessage) and m.content == "안녕" for m in call_messages
        )

    @pytest.mark.asyncio
    async def test_does_not_add_human_message_when_text_empty(self):
        """콜백 경로: text=""이면 HumanMessage를 context에 추가하지 않는다."""
        agent, stm, ltm = _make_deps()
        mock_slack = AsyncMock()

        with (
            patch(
                "src.services.channel_service.load_context",
                new=AsyncMock(return_value=[]),
            ),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch(
                "src.services.channel_service.get_slack_service",
                return_value=mock_slack,
            ),
        ):
            await process_message(
                text="",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        call_messages = agent.invoke.call_args[1]["messages"]
        assert not any(isinstance(m, HumanMessage) for m in call_messages)

    @pytest.mark.asyncio
    async def test_sends_response_to_slack(self):
        agent, stm, ltm = _make_deps("Yuri 응답")
        mock_slack = AsyncMock()

        with (
            patch(
                "src.services.channel_service.load_context",
                new=AsyncMock(return_value=[]),
            ),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch(
                "src.services.channel_service.get_slack_service",
                return_value=mock_slack,
            ),
        ):
            await process_message(
                text="ping",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        mock_slack.send_message.assert_called_once_with("C1", "Yuri 응답")

    @pytest.mark.asyncio
    async def test_sends_error_message_on_invoke_failure(self):
        agent, stm, ltm = _make_deps()
        agent.invoke = AsyncMock(side_effect=RuntimeError("LLM 오류"))
        mock_slack = AsyncMock()

        with (
            patch(
                "src.services.channel_service.load_context",
                new=AsyncMock(return_value=[]),
            ),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch(
                "src.services.channel_service.get_slack_service",
                return_value=mock_slack,
            ),
        ):
            await process_message(
                text="ping",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        mock_slack.send_message.assert_called_once()
        sent_text = mock_slack.send_message.call_args[0][1]
        assert "오류" in sent_text
