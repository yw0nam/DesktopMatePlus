from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from langchain_core.messages import BaseMessage

from src.services.stm_service.utils.image_manager import LocalImageManager

MemoryClientType = TypeVar(
    "MemoryClientType"
)  # A generic type for memory client instances.


class STMService(ABC, Generic[MemoryClientType]):
    """Abstract base class for Short-Term memory services.

    Short Term memory service is responsible for storing and retrieving information
    over brief interactions like chat history and session data.
    Don't handle long-term interactions like user preferences, which are
    managed by Long-Term memory services.

    Currently, STM use DB for backend storage.
    Note, Use openai-compatible message formats for chat history.
    Args:
        memory_config (dict, Optional): Configuration for the memory connection.
    """

    def __init__(self, **kwargs):
        self.image_manager = LocalImageManager(
            base_dir=kwargs.get("base_dir", "static/images")
        )
        self.memory_client = self.initialize_memory()

    @abstractmethod
    def initialize_memory(self) -> MemoryClientType:
        """
        Initialize the short term memory retrieval client.

        Returns:
            MemoryClientType: The initialized short term memory client.
        """

    @abstractmethod
    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the short term memory service is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """

    @abstractmethod
    def add_chat_history(
        self,
        user_id: str,
        agent_id: str,
        session_id: Optional[str],
        messages: list[BaseMessage],
    ) -> str:
        """
        Add chat history. If session_id is None, creates a new session.
        Note
        - use openai-compatible message formats for messages.
        - store images using LocalImageManager before storing messages.

        example:
        ```python
        serialized_messages = convert_to_openai_messages(messages)
        serialized_messages = self.image_manager.process_images(
            serialized_messages, user_id
        )
        After that process the serialized_messages for storage.
        ```
        Args:
            user_id (str): User identifier.
            agent_id (str): Agent identifier.
            session_id (Optional[str]): Session identifier. Creates new session if None.
            messages (list[BaseMessage]): List of messages to add.
        Returns:
            str: The session_id (newly created or existing).
        """

    @abstractmethod
    def get_chat_history(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        limit: Optional[int] = None,
    ) -> list[BaseMessage]:
        """
        Get the chat history.

        Args:
            user_id (str): User identifier.
            agent_id (str): Agent identifier.
            session_id (str): Session identifier.
            limit (Optional[int]): Max number of recent messages to retrieve.
        Returns:
            list[BaseMessage]: Chat history.
        """

    @abstractmethod
    def list_sessions(self, user_id: str, agent_id: str) -> list[dict]:
        """
        Get the list of sessions for a user and agent.

        Args:
            user_id (str): User identifier.
            agent_id (str): Agent identifier.
        Returns:
            list[dict]: List of session metadata (e.g., session_id, created_at, title).
        """

    @abstractmethod
    def delete_session(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """
        Delete a specific chat session and all its messages.

        Args:
            session_id (str): Session identifier.
            user_id (str): User identifier (for verification).
            agent_id (str): Agent identifier (for verification).
        Returns:
            bool: True if deletion was successful.
        """

    @abstractmethod
    def update_session_metadata(self, session_id: str, metadata: dict) -> bool:
        """
        Update the metadata of a specific session (e.g., title, summary).

        Args:
            session_id (str): Session identifier.
            metadata (dict): Metadata to update or add.
        Returns:
            bool: True if update was successful.
        """
