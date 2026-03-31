import subprocess
from dataclasses import dataclass

from loguru import logger


@dataclass
class SearchResult:
    path: str
    content: str


class KnowledgeBaseService:
    def __init__(self, kb_path: str) -> None:
        self.kb_path = kb_path

    def search(self, query: str, tags: list[str]) -> list[SearchResult]:
        """Search knowledge base using rg (ripgrep).

        Note: tags filtering not yet implemented.
        """
        cmd = ["rg", "--with-filename", "--no-heading", "-l", query, self.kb_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode not in (0, 1):
                logger.warning(f"rg error: {result.stderr}")
                return []

            results = []
            for filepath in result.stdout.strip().splitlines():
                filepath = filepath.strip()
                if not filepath:
                    continue
                try:
                    content = self.read(filepath)
                    results.append(SearchResult(path=filepath, content=content))
                except Exception as e:
                    logger.warning(f"Failed to read {filepath}: {e}")
            return results
        except FileNotFoundError:
            logger.error("rg (ripgrep) not found. Install ripgrep.")
            return []

    def read(self, path: str) -> str:
        """Read a file from the knowledge base."""
        with open(path, encoding="utf-8") as f:
            return f.read()
