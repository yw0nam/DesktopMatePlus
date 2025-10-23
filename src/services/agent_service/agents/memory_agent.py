from langchain_core.language_models import BaseChatModel
from mem0 import Memory

from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)


class MemoryAgent:
    """
    Agent that summarizes and update, delete memories.

    """

    def __init__(
        self,
        mem0_client: Memory,
        llm: BaseChatModel,
        vocabulary_manager: PostgreSQLVocabularyManager,
    ):
        self._mem0_client = mem0_client
        self._llm = llm
        self._vocabulary_manager = vocabulary_manager
