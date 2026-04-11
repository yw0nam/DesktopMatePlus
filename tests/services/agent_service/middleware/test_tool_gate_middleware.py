"""Tests for ToolGateMiddleware — defense-in-depth tool call validation."""

from unittest.mock import AsyncMock, MagicMock

from src.services.agent_service.middleware.tool_gate_middleware import (
    ToolGateMiddleware,
)


def _make_request(tool_name: str, args: dict) -> MagicMock:
    """Build a fake ToolCallRequest-like object."""
    request = MagicMock()
    request.tool_call = {"name": tool_name, "args": args}
    return request


async def _pass_through_handler(request):
    return "executed"


class TestShellGating:
    async def test_allowed_command_passes_through(self):
        gate = ToolGateMiddleware(allowed_commands=["ls", "cat"])
        request = _make_request("terminal", {"commands": "ls -la /tmp"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_blocked_command_returns_error(self):
        gate = ToolGateMiddleware(allowed_commands=["ls", "cat"])
        request = _make_request("terminal", {"commands": "rm -rf /"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "rm" in result
        assert "not allowed" in result

    async def test_empty_allowed_commands_is_permissive(self):
        gate = ToolGateMiddleware(allowed_commands=[])
        request = _make_request("terminal", {"commands": "rm -rf /"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_none_allowed_commands_is_permissive(self):
        gate = ToolGateMiddleware(allowed_commands=None)
        request = _make_request("terminal", {"commands": "anything goes"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_blocked_command_message_includes_allowed_list(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "curl http://evil.com"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        assert "curl" in result
        assert "ls" in result

    async def test_empty_command_string_blocked_when_restrictions_set(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": ""})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "not allowed" in result


class TestFilesystemGating:
    async def test_path_within_allowed_dir_passes(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request(
            "read_file", {"file_path": "/tmp/agent-workspace/file.txt"}
        )
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_path_outside_allowed_dir_is_blocked(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("read_file", {"file_path": "/etc/passwd"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "outside the allowed" in result

    async def test_write_file_within_allowed_dir_passes(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request(
            "write_file", {"file_path": "/tmp/agent-workspace/out.txt"}
        )
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_write_file_outside_allowed_dir_is_blocked(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("write_file", {"file_path": "/home/user/.bashrc"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "outside the allowed" in result

    async def test_list_directory_within_allowed_dir_passes(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("list_directory", {"dir_path": "/tmp/agent-workspace"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_list_directory_outside_blocked(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("list_directory", {"dir_path": "/var/log"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "outside the allowed" in result

    async def test_empty_allowed_dirs_is_permissive(self):
        gate = ToolGateMiddleware(allowed_dirs=[])
        request = _make_request("read_file", {"file_path": "/etc/passwd"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_none_allowed_dirs_is_permissive(self):
        gate = ToolGateMiddleware(allowed_dirs=None)
        request = _make_request("write_file", {"file_path": "/etc/shadow"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_path_traversal_blocked(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        # Path traversal attempt that resolves outside allowed dir
        request = _make_request(
            "read_file",
            {"file_path": "/tmp/agent-workspace/../../../etc/passwd"},
        )
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "outside the allowed" in result

    async def test_no_path_arg_passes_through(self):
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("read_file", {})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"


class TestNonGatedTools:
    async def test_memory_tool_passes_through_unaffected(self):
        gate = ToolGateMiddleware(
            allowed_commands=["ls"],
            allowed_dirs=["/tmp/agent-workspace"],
        )
        request = _make_request("save_memory", {"content": "remember this"})
        handler = AsyncMock(return_value="memory_saved")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "memory_saved"

    async def test_delegate_task_tool_passes_through(self):
        gate = ToolGateMiddleware(
            allowed_commands=["ls"],
            allowed_dirs=["/tmp/agent-workspace"],
        )
        request = _make_request("delegate_task", {"task": "do something"})
        handler = AsyncMock(return_value="delegated")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "delegated"

    async def test_web_search_tool_passes_through(self):
        gate = ToolGateMiddleware(
            allowed_commands=["ls"],
            allowed_dirs=["/tmp/agent-workspace"],
        )
        request = _make_request("web_search", {"query": "python docs"})
        handler = AsyncMock(return_value="search_result")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "search_result"


class TestPermissiveDefaults:
    async def test_no_config_allows_all_shell(self):
        gate = ToolGateMiddleware()
        request = _make_request("terminal", {"commands": "rm -rf /"})
        handler = AsyncMock(return_value="executed")

        await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)

    async def test_no_config_allows_all_filesystem(self):
        gate = ToolGateMiddleware()
        request = _make_request("read_file", {"file_path": "/etc/shadow"})
        handler = AsyncMock(return_value="executed")

        await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
