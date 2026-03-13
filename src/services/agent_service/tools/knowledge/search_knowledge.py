from dataclasses import asdict

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict

from src.services.knowledge_base_service.service import KnowledgeBaseService


class SearchKnowledgeInput(BaseModel):
    query: str
    tags: list[str] = []


class SearchKnowledgeTool(BaseTool):
    """Search the knowledge base using ripgrep."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "search_knowledge"
    description: str = (
        "Search the local knowledge base for notes and documents. "
        "Use this to find relevant information stored in the knowledge base."
    )
    args_schema: type[SearchKnowledgeInput] = SearchKnowledgeInput
    service: KnowledgeBaseService

    def _run(self, query: str, tags: list[str] = []) -> list[dict]:  # noqa: B006
        results = self.service.search(query=query, tags=tags)
        return [asdict(r) for r in results]
