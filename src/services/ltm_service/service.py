from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from langchain_core.messages import BaseMessage

MemoryClientType = TypeVar(
    "MemoryClientType"
)  # A generic type for memory client instances.


class LTMService(ABC, Generic[MemoryClientType]):
    """Abstract base class for Long-Term memory services.

    Long Term memory service is responsible for storing and retrieving information over extended periods like preference, context, and user behavior.
    Don't handle short-term interactions like chat history, which are managed by Short-Term memory services.

    """

    def __init__(self):
        self.memory_client = self.initialize_memory()

    @abstractmethod
    def initialize_memory(self) -> MemoryClientType:
        """
        Initialize the long term memory retrieval client.

        Returns:
            MemoryClientType: The initialized long term memory client.
        """

    @abstractmethod
    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the long term memory service is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """

    @abstractmethod
    def search_memory(self, query: str, user_id: str, agent_id: str) -> dict:
        """
        Search the long term memory for relevant information.

        Returns:
            dict: Search results. Note it always have below structure.
                {
                    'results': [ ... ],  # List of memory items
                    'relations': [ ... ] # List of relations extracted from the memory
                }
        """

    @abstractmethod
    def add_memory(
        self, messages: list[BaseMessage], user_id: str, agent_id: str
    ) -> dict:
        """
        Add long term information to memory.

        Returns:
            dict: Add results. Note it always have below structure.
                {
                    'results': [ ... ],  # List of added memory entries
                    'relations': [ ... ] # List of relations extracted from the memory
                }
        """

    @abstractmethod
    def delete_memory(self, user_id: str, agent_id: str, memory_id: str) -> dict:
        """
        Delete long term information from memory.

        Returns:
            dict: Delete results.
        """

    # @abstractmethod
    # def update_memory(self, memory_id: str, user_id: str, agent_id: str, updates: dict) -> dict:
    #     """
    #     Update long term information in memory.

    #     Returns:
    #         dict: Update results.
    #     """
