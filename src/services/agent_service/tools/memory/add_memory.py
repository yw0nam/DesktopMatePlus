import json
from typing import Any, Dict, Iterable, Optional

from langchain_core.tools import BaseTool
from mem0 import Memory

from src.configs.postgresql_config import VOCABULARY_DB_CONFIG
from src.tools.memory.metadata_manager import PostgreSQLVocabularyManager
from src.tools.memory.schemas import AddMemoryInput


class AddMemoryTool(BaseTool):
    """A tool to add a new memory to the user's knowledge base."""

    name: str = "add_memory"
    description: str = (
        "Use this tool to add and store a new piece of information or memory. Provide the content and the user's ID."
    )
    args_schema: type[AddMemoryInput] = AddMemoryInput
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
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Adds a memory synchronously."""
        try:
            self._record_categories(metadata)
            result = self.mem0_client.add(
                content,
                user_id=self.user_id,
                run_id=self.run_id,
                agent_id=self.agent_id,
                metadata=metadata,
            )
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return json.dumps({"error": str(exc)})

    def _record_categories(self, metadata: Optional[Dict[str, Any]]) -> None:
        if not metadata or "category" not in metadata or not self.vocabulary_manager:
            return

        raw_categories = metadata.get("category")
        categories: Iterable[str] = []
        if isinstance(raw_categories, str):
            categories = [raw_categories]
        elif isinstance(raw_categories, (list, tuple, set)):
            categories = [item for item in raw_categories if isinstance(item, str)]
        else:
            return

        cleaned = self.vocabulary_manager.ensure_categories(categories)
        if not cleaned:
            metadata.pop("category", None)
            return

        if isinstance(raw_categories, str) and len(cleaned) == 1:
            metadata["category"] = cleaned[0]
        else:
            metadata["category"] = cleaned
