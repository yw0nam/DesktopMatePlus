from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class SearchResult:
    path: str
    content: str


class KnowledgeBaseService:
    def __init__(self, kb_path: str) -> None:
        self.kb_path = Path(kb_path)

    def search(self, query: str, tags: list[str]) -> list[SearchResult]:
        """Search knowledge base files for query string.

        Note: tags filtering not yet implemented.
        """
        if not self.kb_path.exists():
            logger.warning(f"Knowledge base path does not exist: {self.kb_path}")
            return []

        results: list[SearchResult] = []
        for filepath in sorted(self.kb_path.rglob("*.md")):
            if not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                if query in content:
                    results.append(SearchResult(path=str(filepath), content=content))
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")
        return results

    def read(self, path: str) -> str:
        """Read a file from the knowledge base."""
        with open(path, encoding="utf-8") as f:
            return f.read()
