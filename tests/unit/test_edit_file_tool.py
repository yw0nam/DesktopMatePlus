"""Tests for EditFileTool: unique-match edit with sandbox guard."""

from pathlib import Path

import pytest


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.asyncio
async def test_edit_unique_match(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    (sandbox / "a.txt").write_text("hello world\n")
    tool = EditFileTool(root_dir=str(sandbox))

    result = await tool._arun(file_path="a.txt", old_string="world", new_string="yuri")

    assert "Edited a.txt" in result
    assert (sandbox / "a.txt").read_text() == "hello yuri\n"


@pytest.mark.asyncio
async def test_edit_absent_match(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    (sandbox / "a.txt").write_text("hello\n")
    tool = EditFileTool(root_dir=str(sandbox))

    result = await tool._arun(file_path="a.txt", old_string="XXX", new_string="YYY")

    assert "not found" in result
    assert (sandbox / "a.txt").read_text() == "hello\n"


@pytest.mark.asyncio
async def test_edit_ambiguous_match(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    (sandbox / "a.txt").write_text("foo foo\n")
    tool = EditFileTool(root_dir=str(sandbox))

    result = await tool._arun(file_path="a.txt", old_string="foo", new_string="bar")

    assert "matches 2 times" in result
    assert (sandbox / "a.txt").read_text() == "foo foo\n"


@pytest.mark.asyncio
async def test_edit_rejects_absolute_path(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    tool = EditFileTool(root_dir=str(sandbox))
    result = await tool._arun(file_path="/etc/passwd", old_string="a", new_string="b")

    assert "must be relative" in result


@pytest.mark.asyncio
async def test_edit_rejects_traversal(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    outside = sandbox.parent / "outside.txt"
    outside.write_text("secret\n")
    try:
        tool = EditFileTool(root_dir=str(sandbox))
        result = await tool._arun(
            file_path="../outside.txt", old_string="secret", new_string="LEAKED"
        )
        assert "escapes sandbox" in result
        assert outside.read_text() == "secret\n"
    finally:
        outside.unlink(missing_ok=True)


def test_get_filesystem_tools_returns_eight_tools(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import (
        get_filesystem_tools,
    )

    tools = get_filesystem_tools(root_dir=str(sandbox))
    names = {t.name for t in tools}
    expected = {
        "copy_file",
        "file_delete",
        "file_search",
        "move_file",
        "read_file",
        "write_file",
        "list_directory",
        "edit_file",
    }
    assert names == expected
