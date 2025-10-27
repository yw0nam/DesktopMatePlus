from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import BaseCheckpointSaver


class AgentService(ABC):
    """Abstract base class for agent services.

    Args:
        mcp_config (dict): Configuration for the Multi-Server MCP Client.
        checkpoint_config (dict, optional): Configuration for checkpoint saving.
    """

    def __init__(self, mcp_config: dict = None, checkpoint_config: dict = None):
        self.mcp_config = mcp_config
        self.checkpoint = checkpoint_config

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
        client_id: str = "default_client",
        tools: Optional[list[BaseTool]] = None,
        user_id: str = "default_user",
        agent_id: str = "default_agent",
    ):
        """Generate a response from the model based on the prompt and messages.
        Note, you have to yield stream response following format:

        Yields examples:
            For stream start:
                {
                    "type": "stream_start",
                    "data": {
                        "turn_id": "unique_turn_id",
                        "client_id": client_id,
                    }
                }
            For agent streaming response:
                {
                    "type": "stream_token",
                    "data": "message chunk",
                    "node": "node_id_123",
                }
            For tool call:
                {
                    "type": "tool_call",
                    "data": {
                        "tool_name": "example_tool",
                        "args": "input for the tool",
                    },
                    "node": "node_id_123",
                }
            For tool result:
                {
                    "type": "tool_result",
                    "data": "result from the tool",
                    "node": "node_id_123",
                }
            For stream end:
                {
                    "type": "stream_end",
                    "data": {
                        "turn_id": "unique_turn_id",
                        "client_id": client_id,
                    }
                }
            For error handling:
                {
                    "type": "error",
                    "data": "error message",
                }

        Args:
            messages (list[BaseMessage]): The messages to include in the request.
            client_id (str): Client identifier.
            tools (Optional[list[BaseTool]]): Additional tools for the agent.
            user_id (str): Persistent user identifier for memory tool.
            agent_id (str): Persistent agent identifier for memory tool.

        Yields:
            dict: The model's response stream.
        """
