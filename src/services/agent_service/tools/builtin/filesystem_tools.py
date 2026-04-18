"""Filesystem tools: FileManagementToolkit (disk-backed) + EditFileTool."""

import asyncio
from pathlib import Path

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field


def get_filesystem_tools(root_dir: str) -> list[BaseTool]:
    """Return FileManagementToolkit's 7 tools + EditFileTool, all scoped to root_dir."""
    toolkit_tools = FileManagementToolkit(root_dir=root_dir).get_tools()
    return [*toolkit_tools, EditFileTool(root_dir=root_dir)]


class _EditFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path within root_dir")
    old_string: str = Field(
        ..., description="Exact substring to replace (must occur exactly once)"
    )
    new_string: str = Field(..., description="Replacement string")


class EditFileTool(BaseTool):
    """Edit a file by replacing exactly one occurrence of old_string with new_string."""

    name: str = "edit_file"
    description: str = (
        "Replace a unique substring in a text file. "
        "Fails if old_string is absent or matches more than once."
    )
    args_schema: type[_EditFileInput] = _EditFileInput
    root_dir: str

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use async invocation")

    async def _arun(self, file_path: str, old_string: str, new_string: str) -> str:
        if Path(file_path).is_absolute():
            return "file_path must be relative to the sandbox root."
        root = Path(self.root_dir).resolve()
        target = (root / file_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return "file_path escapes sandbox root."

        content = await asyncio.to_thread(target.read_text, encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return f"old_string not found in {file_path}."
        if count > 1:
            return f"old_string matches {count} times in {file_path}; provide more context."
        await asyncio.to_thread(
            target.write_text,
            content.replace(old_string, new_string, 1),
            encoding="utf-8",
        )
        logger.info(f"edit_file: {file_path} (1 replacement)")
        return f"Edited {file_path}."
