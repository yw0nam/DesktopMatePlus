"""Shell tool wrapper with command whitelist enforcement."""

import subprocess

from langchain_core.tools import BaseTool
from loguru import logger


class RestrictedShellTool(BaseTool):
    """BaseTool that validates commands against a whitelist before execution.

    Only commands whose first token appears in ``allowed_commands`` are executed
    via subprocess. All other commands are rejected with an error message.
    """

    name: str = "terminal"
    description: str = (
        "Run shell commands. Only whitelisted commands are permitted. "
        "Input should be a valid shell command string."
    )
    allowed_commands: list[str]

    def _run(self, commands: str) -> str:  # type: ignore[override]
        """Execute ``commands`` if the leading token is whitelisted.

        Args:
            commands: Shell command string to execute.

        Returns:
            Command stdout/stderr output, or an error message if blocked.
        """
        first_token = commands.strip().split()[0] if commands.strip() else ""
        if first_token not in self.allowed_commands:
            logger.warning(f"Shell command blocked (not allowed): {first_token!r}")
            return (
                f"Command '{first_token}' is not allowed. "
                f"Allowed commands: {self.allowed_commands}"
            )
        logger.info(f"Shell command executing: {commands!r}")
        try:
            result = subprocess.run(
                commands,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += result.stderr
            return output
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as e:
            logger.error(f"Shell command failed: {e}")
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
