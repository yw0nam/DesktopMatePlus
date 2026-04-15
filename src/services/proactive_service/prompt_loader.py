"""YAML-based prompt template loader for proactive triggers."""

from pathlib import Path

import yaml
from loguru import logger

_DEFAULT_PROMPTS_PATH = (
    Path(__file__).resolve().parents[3] / "yaml_files" / "proactive_prompts.yml"
)


class PromptLoader:
    """Loads and renders proactive prompt templates from YAML."""

    def __init__(self, prompts_path: Path | None = None):
        self._path = prompts_path or _DEFAULT_PROMPTS_PATH
        self._templates: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)load prompt templates from YAML file."""
        if not self._path.exists():
            logger.warning(f"Proactive prompts file not found: {self._path}")
            self._templates = {}
            return
        with open(self._path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._templates = {k: str(v) for k, v in data.items()}
        logger.info(f"Loaded {len(self._templates)} proactive prompt templates")

    def render(self, trigger_type: str, **kwargs: object) -> str:
        """Render a prompt template.

        Missing template → fallback string.
        Missing variables → left as placeholder (e.g. {key}).
        """
        template = self._templates.get(trigger_type)
        if template is None:
            logger.warning(f"No prompt template for trigger type: {trigger_type}")
            return f"Proactive trigger: {trigger_type}"
        return template.format_map(_SafeDict(kwargs))


class _SafeDict(dict):
    """Dict subclass that returns '{key}' for missing keys."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
