from abc import ABC, abstractmethod
from typing import Generic, TypeVar

MemoryClientType = TypeVar(
    "MemoryClientType"
)  # A generic type for memory client instances.


class LTMService(ABC, Generic[MemoryClientType]):
    """Abstract base class for Long-Term memory services.

    Long Term memory service is responsible for storing and retrieving information over extended periods like preference, context, and user behavior.
    Don't handle short-term interactions like chat history, which are managed by Short-Term memory services.

    Args:
        memory_config (dict, optional): Configuration for Long-Term memory saving.
    """

    def __init__(self, memory_config: dict = None):
        self.memory_config = memory_config
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
    def search_memory(self, query: str) -> dict:
        """
        Search the long term memory for relevant information.

        Returns:
            dict: Search results.
        """

    @abstractmethod
    def add_memory(self) -> dict:
        """
        Add long term information to memory.

        Returns:
            dict: Add results.
        """
