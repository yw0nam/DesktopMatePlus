"""ToolGateMiddleware — defense-in-depth validation of tool calls before execution."""

from pathlib import Path

from langchain.agents.middleware.types import AgentMiddleware
from loguru import logger

# Tool names for shell and filesystem tools
_SHELL_TOOL_NAME = "terminal"
_FILESYSTEM_TOOL_NAMES = frozenset(["read_file", "write_file", "list_directory"])


class ToolGateMiddleware(AgentMiddleware):
    """Validates tool calls against whitelist/path restrictions before execution.

    This is a defense-in-depth layer. Even if tool-level restrictions are bypassed,
    this middleware blocks dangerous calls at the middleware level.

    Shell calls: the leading command token must be in ``allowed_commands``.
    Filesystem calls: the target path must resolve within one of ``allowed_dirs``.
    All other tools pass through unaffected.

    When no restrictions are configured (empty lists), the middleware is permissive
    and allows all calls.
    """

    def __init__(
        self,
        allowed_commands: list[str] | None = None,
        allowed_dirs: list[str] | None = None,
    ) -> None:
        self._allowed_commands: list[str] = allowed_commands or []
        self._allowed_dirs: list[str] = allowed_dirs or []

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
        if not self._allowed_commands:
            # No restriction configured — permissive
            return None

        command_str: str = args.get("commands", "")
        first_token = command_str.strip().split()[0] if command_str.strip() else ""

        if first_token not in self._allowed_commands:
            logger.warning(
                f"ToolGate blocked shell command: first_token={first_token!r} "
                f"allowed={self._allowed_commands}"
            )
            return (
                f"Command '{first_token}' is not allowed. "
                f"Allowed commands: {self._allowed_commands}"
            )
        return None

    def _check_filesystem(self, tool_name: str, args: dict) -> str | None:
        """Return an error string if the filesystem path is blocked, else None."""
        if not self._allowed_dirs:
            # No restriction configured — permissive
            return None

        # read_file / write_file use "file_path"; list_directory uses "dir_path"
        raw_path: str = args.get("file_path") or args.get("dir_path") or ""
        if not raw_path:
            # No path argument — let the tool handle it
            return None

        try:
            resolved = Path(raw_path).resolve()
        except Exception:
            logger.warning(
                f"ToolGate blocked filesystem call: unresolvable path {raw_path!r}"
            )
            return f"Path '{raw_path}' could not be resolved."

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
        return f"Path '{raw_path}' is outside the allowed directories: {self._allowed_dirs}"
