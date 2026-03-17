from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from loguru import logger

from src.services.ltm_service import LTMService
from src.services.stm_service import STMService


class AgentService(ABC):
    """Abstract base class for agent services."""

    def __init__(
        self,
        mcp_config: dict = None,
        support_image: bool = False,
    ):
        self.mcp_config = mcp_config
        self.support_image = support_image
        self.llm = self.initialize_model()

    @abstractmethod
    def initialize_model(self) -> BaseChatModel:
        """Initialize and return the language model."""

    async def initialize_async(self) -> None:
        """Async initialization: MCP tool fetch + agent creation. Default: no-op."""
        pass

    @abstractmethod
    async def is_healthy(self) -> tuple[bool, str]:
        """Check if the Agent is healthy and ready."""

    @abstractmethod
    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        stm_service: Optional[STMService] = None,
        ltm_service: Optional[LTMService] = None,
    ):
        """Stream agent response.

        Yields dicts with type: stream_start | stream_token | tool_call |
        tool_result | stream_end | error
        """

    LTM_CONSOLIDATION_TURN_INTERVAL = 10

    async def save_memory(
        self,
        new_chats: list[BaseMessage],
        stm_service: STMService,
        ltm_service: LTMService,
        user_id: str,
        agent_id: str,
        session_id: str,
    ):
        """Save new chats to STM and conditionally consolidate to LTM.

        Fire-and-forget background task via asyncio.create_task().
        """
        import asyncio

        try:
            if new_chats and stm_service:
                await asyncio.to_thread(
                    stm_service.add_chat_history,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    messages=new_chats,
                )
                logger.info(f"Chat history saved to STM: {session_id}")

            if ltm_service and stm_service:
                metadata = await asyncio.to_thread(
                    stm_service.get_session_metadata, session_id
                )
                last_consolidated = metadata.get("ltm_last_consolidated_at_turn", 0)

                history = await asyncio.to_thread(
                    stm_service.get_chat_history,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                )
                current_turn = sum(1 for m in history if isinstance(m, HumanMessage))

                if (
                    current_turn - last_consolidated
                    >= self.LTM_CONSOLIDATION_TURN_INTERVAL
                ):
                    slice_start = 0
                    human_count = 0
                    for idx, msg in enumerate(history):
                        if isinstance(msg, HumanMessage):
                            if human_count == last_consolidated:
                                slice_start = idx
                                break
                            human_count += 1
                    else:
                        slice_start = len(history)
                    messages_since_last = history[slice_start:]
                    ltm_result = await asyncio.to_thread(
                        ltm_service.add_memory,
                        messages=messages_since_last,
                        user_id=user_id,
                        agent_id=agent_id,
                    )
                    await asyncio.to_thread(
                        stm_service.update_session_metadata,
                        session_id,
                        {"ltm_last_consolidated_at_turn": current_turn},
                    )
                    logger.info(
                        f"LTM consolidation triggered at turn {current_turn}: {ltm_result}"
                    )

            logger.info(f"Memory save completed for session {session_id}")
        except Exception as e:
            logger.error(f"Background memory save failed for session {session_id}: {e}")
