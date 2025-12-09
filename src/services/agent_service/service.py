import logging
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import BaseCheckpointSaver

from src.services.ltm_service import LTMService
from src.services.stm_service import STMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentService(ABC):
    """Abstract base class for agent services.

    Args:
        mcp_config (dict): Configuration for the Multi-Server MCP Client.
        checkpoint_config (dict, optional): Configuration for checkpoint saving.
    """

    def __init__(
        self,
        mcp_config: dict = None,
        checkpoint_config: dict = None,
        support_image: bool = False,
    ):
        self.mcp_config = mcp_config
        self.checkpoint = checkpoint_config
        self.support_image = support_image

        self.llm, self.checkpoint = self.initialize_model()

    @abstractmethod
    def initialize_model(self) -> tuple[BaseChatModel, BaseCheckpointSaver]:
        """
        Initialize the language model and checkpoint saver.

        Returns:
            tuple[BaseChatModel, BaseCheckpointSaver]: The initialized model and checkpoint saver.
        """

    @abstractmethod
    async def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the Agent is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """

    @abstractmethod
    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        tools: Optional[list[BaseTool]] = None,
        persona: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        stm_service: Optional[STMService] = None,
        ltm_service: Optional[LTMService] = None,
    ):
        """Generate a response from the model based on the prompt and messages.
        Note, you have to yield stream response following format:

        Yields examples:
            For stream start:
                {
                    "type": "stream_start",
                    "turn_id": "unique_turn_id",
                    "session_id": session_id,
                }
            For agent streaming response:
                {
                    "type": "stream_token",
                    "chunk": "message chunk",
                    "node": "node_id_123",
                }
            For tool call:
                {
                    "type": "tool_call",
                    "tool_name": "example_tool",
                    "args": "input for the tool",
                    "node": "node_id_123",
                }
            For tool result:
                {
                    "type": "tool_result",
                    "result": "result from the tool",
                    "node": "node_id_123",
                }
            For stream end:
                {
                    "type": "stream_end",
                    "turn_id": "unique_turn_id",
                    "session_id": session_id,
                    "content": "final complete message",
                }
            For error handling:
                {
                    "type": "error",
                    "error": "error message",
                }

        Args:
            messages (list[BaseMessage]): The messages to include in the request.
            session_id (str): conversation  identifier.
            tools (Optional[list[BaseTool]]): Additional tools for the agent.
            user_id (str): Persistent user identifier for memory tool.
            agent_id (str): Persistent agent identifier for memory tool.
            ltm_service (Optional[LTMService]): Long-Term memory service instance.
            stm_service (Optional[STMService]): Short-Term memory service instance.

        Yields:
            dict: The model's response stream.
        """

    def save_memory(
        self,
        new_chats: list[BaseMessage],
        stm_service: STMService,
        ltm_service: LTMService,
        user_id: str,
        agent_id: str,
        session_id: str,
    ):
        """Save new chats to memory asynchronously.

        This method runs in the background and does not block the response stream.
        Uses asyncio.to_thread() to run blocking I/O operations in a thread pool.
        Errors are logged but do not affect the client response.

        Args:
            new_chats (list[BaseMessage]): New chat messages to save.
            stm_service (STMService): Short-Term memory service instance.
            ltm_service (LTMService): Long-Term memory service instance.
            user_id (str): Persistent user identifier for memory tool.
            agent_id (str): Persistent agent identifier for memory tool.
            session_id (str): Session identifier for the current conversation.
        """

        try:
            if new_chats != [] and stm_service:
                # Run blocking STM operation in thread pool
                session_id = stm_service.add_chat_history(
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    messages=new_chats,
                )
                logger.info("Chat history saved to STM: %s", session_id)
            # if new_chats != [] and ltm_service:
            #     # Run blocking LTM operation in thread pool
            #     # TODO: Need to be optimized this part.
            #     # Add persona information to memory?...
            #     ltm_result = ltm_service.add_memory(
            #         messages=new_chats,
            #         user_id=user_id,
            #         agent_id=agent_id,
            #     )
            #     logger.info("Memory added to LTM: %s", ltm_result)
            logger.info("Memory save completed for session %s", session_id)
            return session_id
        except Exception as e:
            logger.error(
                "Background memory save failed for session %s: %s", session_id, e
            )

    async def async_save_memory(
        self,
        new_chats: list[BaseMessage],
        stm_service: STMService,
        ltm_service: LTMService,
        user_id: str,
        agent_id: str,
        session_id: str,
    ):
        """Save new chats to memory asynchronously.

        This method runs in the background and does not block the response stream.
        Uses asyncio.to_thread() to run blocking I/O operations in a thread pool.
        Errors are logged but do not affect the client response.

        Args:
            new_chats (list[BaseMessage]): New chat messages to save.
            stm_service (STMService): Short-Term memory service instance.
            ltm_service (LTMService): Long-Term memory service instance.
            user_id (str): Persistent user identifier for memory tool.
            agent_id (str): Persistent agent identifier for memory tool.
            session_id (str): Session identifier for the current conversation.
        """
        import asyncio

        try:
            if new_chats != [] and stm_service:
                # Run blocking STM operation in thread pool
                stm_result = await asyncio.to_thread(
                    stm_service.add_chat_history,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    messages=new_chats,
                )
                logger.info("Chat history saved to STM: %s", stm_result)
            # if new_chats != [] and ltm_service:
            #     # Run blocking LTM operation in thread pool
            #     # TODO: Need to be optimized this part.
            #     # Add persona information to memory?...
            #     ltm_result = await asyncio.to_thread(
            #         ltm_service.add_memory,
            #         messages=new_chats,
            #         user_id=user_id,
            #         agent_id=agent_id,
            #     )
            #     logger.info("Memory added to LTM: %s", ltm_result)
            logger.info("Memory save completed for session %s", session_id)
        except Exception as e:
            logger.error(
                "Background memory save failed for session %s: %s", session_id, e
            )
