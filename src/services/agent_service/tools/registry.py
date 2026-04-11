"""Tool registry that instantiates enabled builtin tools from YAML config."""

from langchain_core.tools import BaseTool
from loguru import logger


class ToolRegistry:
    """Instantiates and returns enabled tools based on a ``tool_config`` dict.

    The registry reads the ``builtin`` section of the config and instantiates
    only the tools whose ``enabled`` flag is ``True``.

    Example config structure::

        tool_config:
          builtin:
            filesystem:
              enabled: false
              root_dir: "/tmp/agent-workspace"
            shell:
              enabled: false
              allowed_commands: ["ls", "cat"]
            web_search:
              enabled: false
    """

    def __init__(self, tool_config: dict | None) -> None:
        self._tool_config = tool_config or {}

    def get_enabled_tools(self) -> list[BaseTool]:
        """Return all enabled builtin tools as a flat list.

        Returns:
            List of BaseTool instances for each enabled category.
        """
        builtin: dict = self._tool_config.get("builtin", {})
        if not builtin:
            return []

        tools: list[BaseTool] = []

        fs_cfg: dict = builtin.get("filesystem", {})
        if fs_cfg.get("enabled"):
            from src.services.agent_service.tools.builtin.filesystem_tools import (
                get_filesystem_tools,
            )

            root_dir: str = fs_cfg.get("root_dir", "/tmp/agent-workspace")
            tools.extend(get_filesystem_tools(root_dir=root_dir))
            logger.info("ToolRegistry: filesystem tools added")

        shell_cfg: dict = builtin.get("shell", {})
        if shell_cfg.get("enabled"):
            from src.services.agent_service.tools.builtin.shell_tools import (
                get_shell_tools,
            )

            allowed: list[str] = shell_cfg.get("allowed_commands", [])
            tools.extend(get_shell_tools(allowed_commands=allowed))
            logger.info("ToolRegistry: shell tool added")

        search_cfg: dict = builtin.get("web_search", {})
        if search_cfg.get("enabled"):
            from src.services.agent_service.tools.builtin.search_tools import (
                get_search_tools,
            )

            tools.extend(get_search_tools())
            logger.info("ToolRegistry: web search tool added")

        return tools
