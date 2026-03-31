from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict

from src.services.knowledge_base_service.service import KnowledgeBaseService


class ReadNoteInput(BaseModel):
    path: str


class ReadNoteTool(BaseTool):
    """Read a specific note from the knowledge base."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "read_note"
    description: str = (
        "Read the full content of a specific note from the knowledge base. "
        "Use the path returned by search_knowledge."
    )
    args_schema: type[ReadNoteInput] = ReadNoteInput
    service: KnowledgeBaseService

    def _run(self, path: str) -> str:
        return self.service.read(path)
