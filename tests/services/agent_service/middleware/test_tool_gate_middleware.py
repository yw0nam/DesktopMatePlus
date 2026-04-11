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
        assert "not permitted" in result

    async def test_empty_allowed_commands_denies_all(self):
        """allowed_commands=[] is active but nothing allowed — fail-closed."""
        gate = ToolGateMiddleware(allowed_commands=[])
        request = _make_request("terminal", {"commands": "rm -rf /"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "not permitted" in result

    async def test_none_allowed_commands_is_inactive(self):
        """allowed_commands=None means middleware is inactive — no gating."""
        gate = ToolGateMiddleware(allowed_commands=None)
        request = _make_request("terminal", {"commands": "anything goes"})
        handler = AsyncMock(return_value="executed")

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "executed"

    async def test_blocked_command_message_does_not_leak_whitelist(self):
        """Error messages must not reveal the allowed command list."""
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "curl http://evil.com"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        assert "curl" in result
        # The whitelist itself must NOT appear in the error message
        assert "['ls']" not in result
        assert "allowed_commands" not in result

    async def test_empty_command_string_blocked_when_restrictions_set(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": ""})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert result  # some error message returned


class TestShellBypassPrevention:
    """Tests that shell metacharacter injection attacks are blocked."""

    async def test_semicolon_chaining_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "ls; rm -rf /"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "disallowed shell characters" in result

    async def test_double_ampersand_chaining_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "ls && cat /etc/passwd"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "disallowed shell characters" in result

    async def test_pipe_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "ls | xargs rm"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "disallowed shell characters" in result

    async def test_subshell_dollar_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "ls $(whoami)"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "disallowed shell characters" in result

    async def test_backtick_subshell_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "ls `id`"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "disallowed shell characters" in result

    async def test_newline_injection_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "ls\nrm -rf /"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "disallowed shell characters" in result

    async def test_empty_command_blocked(self):
        gate = ToolGateMiddleware(allowed_commands=["ls"])
        request = _make_request("terminal", {"commands": "   "})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert result  # some error message returned


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

    async def test_empty_allowed_dirs_denies_all(self):
        """allowed_dirs=[] is active but nothing allowed — fail-closed."""
        gate = ToolGateMiddleware(allowed_dirs=[])
        request = _make_request("read_file", {"file_path": "/etc/passwd"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert result  # some error message returned

    async def test_none_allowed_dirs_is_inactive(self):
        """allowed_dirs=None means middleware is inactive — no gating."""
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

    async def test_missing_path_arg_is_blocked(self):
        """Filesystem tool called without a path argument must be blocked."""
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("read_file", {})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert result  # some error message returned

    async def test_error_message_does_not_leak_allowed_dirs(self):
        """Error messages must not reveal the allowed_dirs list."""
        gate = ToolGateMiddleware(allowed_dirs=["/tmp/agent-workspace"])
        request = _make_request("read_file", {"file_path": "/etc/passwd"})
        handler = AsyncMock()

        result = await gate.awrap_tool_call(request, handler)

        assert "/tmp/agent-workspace" not in result
        assert "allowed_dirs" not in result


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
        """Default (None, None) — middleware fully inactive."""
        gate = ToolGateMiddleware()
        request = _make_request("terminal", {"commands": "rm -rf /"})
        handler = AsyncMock(return_value="executed")

        await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)

    async def test_no_config_allows_all_filesystem(self):
        """Default (None, None) — middleware fully inactive."""
        gate = ToolGateMiddleware()
        request = _make_request("read_file", {"file_path": "/etc/shadow"})
        handler = AsyncMock(return_value="executed")

        await gate.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)
