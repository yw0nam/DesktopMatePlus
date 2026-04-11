"""Shell tool wrapper with command whitelist enforcement."""

import re
import shlex
import subprocess

from langchain_core.tools import BaseTool
from loguru import logger

_DANGEROUS_SHELL_CHARS = re.compile(r"[;&|`$\n(){}<>!]")


class RestrictedShellTool(BaseTool):
    """BaseTool that validates commands against a whitelist before execution.

    Only commands whose first token appears in ``allowed_commands`` are executed
    via subprocess. All other commands are rejected with an error message.
    Shell metacharacters are rejected to prevent injection attacks.
    """

    name: str = "terminal"
    description: str = (
        "Run shell commands. Only whitelisted commands are permitted. "
        "Input should be a valid shell command string."
    )
    allowed_commands: list[str]

    def _run(self, query: str, **kwargs: object) -> str:
        """Execute ``query`` if the leading token is whitelisted.

        Args:
            query: Shell command string to execute.

        Returns:
            Command stdout/stderr output, or an error message if blocked.
        """
        commands = query
        if not commands.strip():
            return "Empty command is not allowed."

        if _DANGEROUS_SHELL_CHARS.search(commands):
            logger.warning("Shell command blocked (dangerous characters detected)")
            return "Command contains disallowed shell characters."

        try:
            tokens = shlex.split(commands)
        except ValueError:
            return "Command could not be parsed."

        if not tokens or tokens[0] not in self.allowed_commands:
            first = tokens[0] if tokens else ""
            logger.warning(f"Shell command blocked (not allowed): {first!r}")
            return (
                f"Command '{first}' is not permitted by security policy. "
                f"Allowed commands: {self.allowed_commands}"
            )

        logger.info(f"Shell command executing: {commands!r}")
        try:
            result = subprocess.run(
                tokens,
                shell=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                if output and not output.endswith("\n"):
                    output += "\n"
                output += result.stderr
            return output
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as e:
            logger.exception(f"Shell command failed: {e}")
            return f"Command failed: {e}"


def get_shell_tools(allowed_commands: list[str]) -> list[BaseTool]:
    """Return a single RestrictedShellTool enforcing the given whitelist.

    Args:
        allowed_commands: List of command names (first tokens) that are permitted.

    Returns:
        List containing one RestrictedShellTool.
    """
    logger.info(f"Shell tool enabled (allowed_commands={allowed_commands})")
    return [RestrictedShellTool(allowed_commands=allowed_commands)]
