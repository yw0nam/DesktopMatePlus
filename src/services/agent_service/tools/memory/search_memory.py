import json
from typing import Any, Dict, Optional

from langchain_core.tools import BaseTool
from mem0 import Memory

from src.configs.postgresql_config import VOCABULARY_DB_CONFIG
from src.tools.memory.metadata_manager import PostgreSQLVocabularyManager
from src.tools.memory.schemas import SearchMemoryInput


class SearchMemoryTool(BaseTool):
    """A tool to search for relevant memories from the user's knowledge base."""

    name: str = "search_memory"
    description: str = (
        "Use this tool to search for memories based on a natural language query. You must provide the user's ID."
    )
    args_schema: type[SearchMemoryInput] = SearchMemoryInput
    mem0_client: Memory
    user_id: str
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    vocabulary_manager: Optional[PostgreSQLVocabularyManager] = None

    def __init__(
        self,
        *,
        mem0_client: Memory,
        user_id: str,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        vocabulary_manager: Optional[PostgreSQLVocabularyManager] = None,
    ) -> None:
        super().__init__(
            mem0_client=mem0_client,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            vocabulary_manager=vocabulary_manager,
        )
        self.mem0_client = mem0_client
        self.user_id = user_id
        self.agent_id = agent_id
        self.run_id = run_id
        self.vocabulary_manager = vocabulary_manager or PostgreSQLVocabularyManager(
            VOCABULARY_DB_CONFIG
        )

    def _run(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Searches for memories synchronously."""
        try:
            normalized_metadata = self._prepare_metadata_filter(metadata_filter)
            search_response = self.mem0_client.search(
                query=query,
                user_id=self.user_id,
                run_id=self.run_id,
                agent_id=self.agent_id,
                limit=limit,
                filters=(
                    {"metadata": normalized_metadata} if normalized_metadata else None
                ),
            )

            return json.dumps(search_response, indent=2, ensure_ascii=False)

        except Exception as e:
            return f"Error searching memory: {e}"

    def _prepare_metadata_filter(
        self, metadata_filter: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not metadata_filter or not self.vocabulary_manager:
            return metadata_filter

        prepared: Dict[str, Any] = dict(metadata_filter)
        if "category" not in prepared:
            return prepared

        raw_categories = prepared.get("category")
        if isinstance(raw_categories, str):
            categories = [raw_categories]
        elif isinstance(raw_categories, (list, tuple, set)):
            categories = [item for item in raw_categories if isinstance(item, str)]
        else:
            prepared.pop("category", None)
            return prepared

        cleaned = self.vocabulary_manager.ensure_categories(categories)
        if not cleaned:
            prepared.pop("category", None)
        elif isinstance(raw_categories, str) and len(cleaned) == 1:
            prepared["category"] = cleaned[0]
        else:
            prepared["category"] = cleaned

        return prepared
