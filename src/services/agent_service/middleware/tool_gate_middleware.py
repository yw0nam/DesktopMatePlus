"""ToolGateMiddleware — defense-in-depth validation of tool calls before execution."""

import re
import shlex
from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware
from loguru import logger

# Tool names for shell and filesystem tools
_SHELL_TOOL_NAME = "terminal"
_FILESYSTEM_TOOL_NAMES = frozenset(["read_file", "write_file", "list_directory"])

# Shell metacharacters that enable command chaining, pipes, subshells, etc.
_DANGEROUS_SHELL_CHARS = re.compile(r"[;&|`$\n\\\"'(){}<>!]")


class ToolGateMiddleware(AgentMiddleware):
    """Validates tool calls against whitelist/path restrictions before execution.

    This is a defense-in-depth layer. Even if tool-level restrictions are bypassed,
    this middleware blocks dangerous calls at the middleware level.

    Shell calls: the leading command token must be in ``allowed_commands``.
    Filesystem calls: the target path must resolve within one of ``allowed_dirs``.
    All other tools pass through unaffected.

    ``allowed_commands=None`` / ``allowed_dirs=None`` — middleware inactive for that
    category (no gating applied).
    ``allowed_commands=[]`` / ``allowed_dirs=[]`` — active but nothing is allowed;
    every call in that category is denied (fail-closed).
    """

    def __init__(
        self,
        allowed_commands: list[str] | None = None,
        allowed_dirs: list[str] | None = None,
    ) -> None:
        # Preserve None vs [] distinction — None means inactive, [] means deny all
        self._allowed_commands: list[str] | None = allowed_commands
        self._allowed_dirs: list[str] | None = allowed_dirs

    async def awrap_tool_call(self, request, handler):  # type: ignore[override]
        tool_name: str = request.tool_call["name"]
        args: dict = request.tool_call.get("args", {})

        if tool_name == _SHELL_TOOL_NAME:
            block_msg = self._check_shell(args)
            if block_msg is not None:
                return block_msg

        if tool_name in _FILESYSTEM_TOOL_NAMES:
            block_msg = self._check_filesystem(tool_name, args)
            if block_msg is not None:
                return block_msg

        return await handler(request)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_shell(self, args: dict) -> str | None:
        """Return an error string if the shell command is blocked, else None."""
        if self._allowed_commands is None:
            return None  # middleware inactive for shell

        command_str: str = args.get("commands", "")
        if not command_str.strip():
            logger.warning("ToolGate blocked empty shell command")
            return "Empty command is not allowed."

        # Reject shell metacharacters that enable chaining, pipes, subshells, etc.
        if _DANGEROUS_SHELL_CHARS.search(command_str):
            logger.warning(f"ToolGate blocked shell metacharacters in: {command_str!r}")
            return "Command contains disallowed shell characters."

        try:
            tokens = shlex.split(command_str)
        except ValueError:
            logger.warning(f"ToolGate blocked unparseable command: {command_str!r}")
            return "Command could not be parsed."

        first_token = tokens[0] if tokens else ""

        if first_token not in self._allowed_commands:
            logger.warning(
                f"ToolGate blocked command: {first_token!r}, "
                f"allowed={self._allowed_commands}"
            )
            return f"Command '{first_token}' is not permitted by security policy."

        return None

    def _check_filesystem(self, tool_name: str, args: dict) -> str | None:
        """Return an error string if the filesystem path is blocked, else None."""
        if self._allowed_dirs is None:
            return None  # middleware inactive for filesystem

        # read_file / write_file use "file_path"; list_directory uses "dir_path"
        raw_path: str = args.get("file_path") or args.get("dir_path") or ""
        if not raw_path:
            logger.warning(
                f"ToolGate blocked filesystem tool called without path: {tool_name!r}"
            )
            return "Filesystem tool called without a recognized path argument."

        try:
            resolved = Path(raw_path).resolve()
        except Exception:
            logger.warning(
                f"ToolGate blocked filesystem call: unresolvable path {raw_path!r}"
            )
            return "Path could not be resolved."

        for allowed in self._allowed_dirs:
            try:
                resolved.relative_to(Path(allowed).resolve())
                return None  # within an allowed dir
            except ValueError:
                continue

        logger.warning(
            f"ToolGate blocked filesystem call: tool={tool_name!r} "
            f"path={str(resolved)!r} allowed_dirs={self._allowed_dirs}"
        )
        return "Path is outside the allowed directories."
