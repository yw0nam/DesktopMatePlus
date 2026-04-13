"""Filesystem tools backed by LangChain community file management tools."""

from langchain_community.tools.file_management import (
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)
from langchain_core.tools import BaseTool


def get_filesystem_tools(root_dir: str) -> list[BaseTool]:
    """Return ReadFileTool, WriteFileTool, and ListDirectoryTool scoped to root_dir.

    Args:
        root_dir: Filesystem path that all file operations are restricted to.

    Returns:
        List of three BaseTool instances for file read, write, and list.
    """
    return [
        ReadFileTool(root_dir=root_dir),
        WriteFileTool(root_dir=root_dir),
        ListDirectoryTool(root_dir=root_dir),
    ]
