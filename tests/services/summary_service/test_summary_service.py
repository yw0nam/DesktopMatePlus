"""Tests for SummaryService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.models.conversation_summary import ConversationSummary
from src.services.summary_service import SummaryService


@pytest.fixture
def mock_collection():
    return MagicMock()


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="This is a test summary.")
    return llm


@pytest.fixture
def service(mock_collection, mock_llm):
    return SummaryService(collection=mock_collection, llm=mock_llm)


@pytest.fixture
def sample_messages():
    return [
        HumanMessage(content="Hello, how are you?"),
        AIMessage(content="I'm doing great, thanks!"),
        HumanMessage(content="What's the weather like?"),
        AIMessage(content="It's sunny and warm today."),
    ]


class TestSummarize:
    async def test_returns_conversation_summary(self, service, sample_messages):
        result = await service.summarize(
            messages=sample_messages,
            session_id="user1:agent1",
            turn_range_start=0,
            turn_range_end=2,
        )

        assert isinstance(result, ConversationSummary)
        assert result.session_id == "user1:agent1"
        assert result.summary_text == "This is a test summary."
        assert result.turn_range_start == 0
        assert result.turn_range_end == 2

    async def test_calls_llm_with_conversation_text(
        self, service, sample_messages, mock_llm
    ):
        await service.summarize(
            messages=sample_messages,
            session_id="user1:agent1",
        )

        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]
        prompt_text = call_args[0].content
        assert "Hello, how are you?" in prompt_text
        assert "I'm doing great, thanks!" in prompt_text
        assert "User:" in prompt_text
        assert "Assistant:" in prompt_text

    async def test_filters_system_messages(self, service, mock_llm):
        messages = [
            SystemMessage(content="You are Yuri."),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi!"),
        ]
        await service.summarize(messages=messages, session_id="s1")

        prompt_text = mock_llm.ainvoke.call_args[0][0][0].content
        assert "You are Yuri." not in prompt_text

    async def test_sets_created_at(self, service, sample_messages):
        result = await service.summarize(messages=sample_messages, session_id="s1")
        assert isinstance(result.created_at, datetime)

    async def test_turn_range_filters_messages(self, service, mock_llm):
        messages = [
            SystemMessage(content="You are Yuri."),
            HumanMessage(content="Turn 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Turn 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Turn 3"),
            AIMessage(content="Response 3"),
        ]
        await service.summarize(
            messages=messages,
            session_id="s1",
            turn_range_start=1,
            turn_range_end=2,
        )

        prompt_text = mock_llm.ainvoke.call_args[0][0][0].content
        assert "Turn 2" in prompt_text
        assert "Response 2" in prompt_text
        assert "Turn 3" not in prompt_text
        assert "Response 3" not in prompt_text
        assert "Turn 1" not in prompt_text
        assert "Response 1" not in prompt_text

    async def test_turn_range_zero_uses_all_messages(self, service, mock_llm):
        messages = [
            HumanMessage(content="Turn 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Turn 2"),
            AIMessage(content="Response 2"),
        ]
        await service.summarize(
            messages=messages,
            session_id="s1",
            turn_range_start=0,
            turn_range_end=0,
        )

        prompt_text = mock_llm.ainvoke.call_args[0][0][0].content
        assert "Turn 1" in prompt_text
        assert "Turn 2" in prompt_text

    async def test_turn_range_includes_system_messages(self, service, mock_llm):
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Turn 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Turn 2"),
            AIMessage(content="Response 2"),
        ]
        await service.summarize(
            messages=messages,
            session_id="s1",
            turn_range_start=0,
            turn_range_end=1,
        )

        prompt_text = mock_llm.ainvoke.call_args[0][0][0].content
        assert "System prompt" not in prompt_text
        assert "Turn 1" in prompt_text


class TestGetSummaries:
    def test_returns_empty_when_no_docs(self, service, mock_collection):
        mock_collection.find.return_value = []
        result = service.get_summaries("user1:agent1")
        assert result == []

    def test_returns_summaries_ordered_by_turn(self, service, mock_collection):
        docs = [
            {
                "session_id": "user1:agent1",
                "summary_text": "First chunk.",
                "turn_range_start": 0,
                "turn_range_end": 20,
                "created_at": datetime.now(UTC),
            },
            {
                "session_id": "user1:agent1",
                "summary_text": "Second chunk.",
                "turn_range_start": 20,
                "turn_range_end": 40,
                "created_at": datetime.now(UTC),
            },
        ]
        mock_collection.find.return_value = docs
        result = service.get_summaries("user1:agent1")

        assert len(result) == 2
        assert all(isinstance(s, ConversationSummary) for s in result)
        assert result[0].summary_text == "First chunk."
        assert result[1].summary_text == "Second chunk."

    def test_queries_by_session_id(self, service, mock_collection):
        mock_collection.find.return_value = []
        service.get_summaries("user1:agent1")
        call_args = mock_collection.find.call_args
        assert call_args[0][0] == {"session_id": "user1:agent1"}


class TestStoreSummary:
    def test_inserts_to_collection(self, service, mock_collection):
        summary = ConversationSummary(
            session_id="user1:agent1",
            summary_text="A summary.",
            turn_range_start=0,
            turn_range_end=20,
        )
        service.store_summary(summary)

        mock_collection.insert_one.assert_called_once()
        inserted = mock_collection.insert_one.call_args[0][0]
        assert inserted["session_id"] == "user1:agent1"
        assert inserted["summary_text"] == "A summary."
