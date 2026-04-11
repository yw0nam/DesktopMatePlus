"""Tool registry that instantiates enabled builtin tools from YAML config."""

from langchain_core.tools import BaseTool
from loguru import logger

from src.configs.agent.openai_chat_agent import BuiltinToolConfig, ToolConfig


class ToolRegistry:
    """Instantiates and returns enabled tools based on a ``ToolConfig``.

    The registry reads the ``builtin`` section of the config and instantiates
    only the tools whose ``enabled`` flag is ``True``. Accepts either a
    ``ToolConfig`` instance or a raw dict (which is validated via Pydantic).

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

    def __init__(self, tool_config: ToolConfig | dict | None) -> None:
        if tool_config is None:
            self._config: ToolConfig | None = None
        elif isinstance(tool_config, dict):
            self._config = ToolConfig.model_validate(tool_config)
        else:
            self._config = tool_config

    def get_enabled_tools(self) -> list[BaseTool]:
        """Return all enabled builtin tools as a flat list.

        Returns:
            List of BaseTool instances for each enabled category.
        """
        if self._config is None:
            return []

        builtin: BuiltinToolConfig = self._config.builtin
        tools: list[BaseTool] = []

        if builtin.filesystem.enabled:
            from src.services.agent_service.tools.builtin.filesystem_tools import (
                get_filesystem_tools,
            )

            tools.extend(get_filesystem_tools(root_dir=builtin.filesystem.root_dir))
            logger.info("ToolRegistry: filesystem tools added")

        if builtin.shell.enabled:
            from src.services.agent_service.tools.builtin.shell_tools import (
                get_shell_tools,
            )

            tools.extend(
                get_shell_tools(allowed_commands=builtin.shell.allowed_commands)
            )
            logger.info("ToolRegistry: shell tool added")

        if builtin.web_search.enabled:
            from src.services.agent_service.tools.builtin.search_tools import (
                get_search_tools,
            )

            tools.extend(get_search_tools())
            logger.info("ToolRegistry: web search tool added")

        return tools
