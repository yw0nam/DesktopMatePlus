"""MongoDB-backed conversation summary service with LLM-based compression."""

import asyncio

import pymongo.collection
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from loguru import logger

from src.models.conversation_summary import ConversationSummary

_DEFAULT_MAX_SUMMARY_LENGTH = 500


class SummaryService:
    """Generates and persists conversation summaries for STM compression."""

    def __init__(
        self,
        collection: pymongo.collection.Collection,
        llm: BaseChatModel,
        max_summary_length: int = _DEFAULT_MAX_SUMMARY_LENGTH,
    ) -> None:
        self._col = collection
        self._llm = llm
        self._max_summary_length = max_summary_length

    async def summarize(
        self,
        messages: list[BaseMessage],
        session_id: str,
        turn_range_start: int = 0,
        turn_range_end: int = 0,
    ) -> ConversationSummary:
        """Generate a summary of a conversation slice via LLM.

        Args:
            messages: Conversation messages to summarize.
            session_id: Identifier for the session/thread.
            turn_range_start: First human turn index in the slice.
            turn_range_end: Last human turn index in the slice.

        Returns:
            ConversationSummary with LLM-generated text.
        """
        lines: list[str] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                content = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
                lines.append(f"User: {content}")
            elif isinstance(msg, AIMessage):
                content = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
                lines.append(f"Assistant: {content}")

        conversation_text = "\n".join(lines)
        prompt = (
            f"Summarize the following conversation in {self._max_summary_length} words or less.\n"
            "Focus on key topics, decisions, and context needed to continue the conversation.\n\n"
            f"Conversation:\n{conversation_text}\n\nSummary:"
        )

        response = await asyncio.wait_for(
            self._llm.ainvoke([HumanMessage(content=prompt)]),
            timeout=60,
        )
        summary_text = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )

        logger.info(
            f"Summary generated for session={session_id} "
            f"turns={turn_range_start}-{turn_range_end}"
        )
        return ConversationSummary(
            session_id=session_id,
            summary_text=summary_text,
            turn_range_start=turn_range_start,
            turn_range_end=turn_range_end,
        )

    def get_summaries(self, session_id: str) -> list[ConversationSummary]:
        """Retrieve stored summaries for a session, ordered by turn range.

        Args:
            session_id: Session identifier to look up.

        Returns:
            List of ConversationSummary sorted ascending by turn_range_end.
        """
        docs = list(
            self._col.find(
                {"session_id": session_id},
                {"_id": 0},
                sort=[("turn_range_end", pymongo.ASCENDING)],
            )
        )
        return [ConversationSummary(**doc) for doc in docs]

    def store_summary(self, summary: ConversationSummary) -> None:
        """Persist a summary to MongoDB.

        Args:
            summary: ConversationSummary to store.
        """
        self._col.insert_one(summary.model_dump())
        logger.info(
            f"Summary stored for session={summary.session_id} "
            f"turns={summary.turn_range_start}-{summary.turn_range_end}"
        )
