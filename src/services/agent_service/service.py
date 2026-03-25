from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


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
        context: dict | None = None,
    ):
        """Stream agent response.

        Yields dicts with type:
          stream_start | stream_token | tool_call | tool_result | stream_end | error

        stream_end payload includes ``new_chats: list[BaseMessage]`` — the new
        messages generated during this turn — so callers can persist them.
        """

    @abstractmethod
    async def invoke(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        context: dict | None = None,
    ) -> dict:
        """Invoke agent and return final result without streaming.

        Returns a dict with:
          content: str — final AI response text
          new_chats: list[BaseMessage] — new messages generated this turn
        """
