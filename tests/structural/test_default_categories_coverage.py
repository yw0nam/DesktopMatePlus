"""Structural test: _DEFAULT_CATEGORIES must cover every built-in tool the agent loads."""

from src.configs.agent.openai_chat_agent import (
    BuiltinToolConfig,
    FilesystemToolConfig,
    ShellToolConfig,
    ToolConfig,
    WebSearchToolConfig,
)
from src.services.agent_service.middleware.hitl_middleware import _DEFAULT_CATEGORIES
from src.services.agent_service.tools.registry import ToolRegistry


def _collect_builtin_tool_names() -> set[str]:
    """Instantiate every built-in tool source and return the set of .name values."""
    names: set[str] = set()

    # 1. YAML-gated tools via ToolRegistry (need enabled=True so they instantiate)
    fully_enabled = ToolConfig(
        builtin=BuiltinToolConfig(
            filesystem=FilesystemToolConfig(enabled=True),
            shell=ShellToolConfig(enabled=True, allowed_commands=["ls"]),
            web_search=WebSearchToolConfig(enabled=True),
        )
    )
    for tool in ToolRegistry(fully_enabled).get_enabled_tools():
        names.add(tool.name)

    # 2. Tools registered outside the registry (enumerate explicitly — if new
    # ones are added, extend this list AND _DEFAULT_CATEGORIES).
    from src.services.agent_service.tools.delegate.delegate_task import DelegateTaskTool

    names.add(DelegateTaskTool().name)

    # Memory / knowledge / profile tools are typically registered by tool-name
    # constants in their modules. Pin them here so drift is caught.
    for fixed in (
        "add_memory",
        "update_memory",
        "delete_memory",
        "search_memory",
        "search_knowledge",
        "read_note",
        "update_user_profile",
    ):
        names.add(fixed)

    return names


def test_default_categories_covers_every_builtin_tool():
    tool_names = _collect_builtin_tool_names()
    missing = tool_names - set(_DEFAULT_CATEGORIES.keys())
    assert not missing, (
        f"_DEFAULT_CATEGORIES missing entries for: {sorted(missing)}. "
        "Add them in src/services/agent_service/middleware/hitl_middleware.py. "
        "See the operator guide in the Phase 2 spec."
    )
