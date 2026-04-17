"""Unit tests for _build_hitl_category_map."""

from src.configs.agent.openai_chat_agent import (
    BuiltinToolConfig,
    FilesystemToolConfig,
    ToolConfig,
    WebSearchToolConfig,
)
from src.models.websocket import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import _DEFAULT_CATEGORIES
from src.services.agent_service.openai_chat_agent import _build_hitl_category_map


class TestBuildHitLCategoryMap:
    def test_defaults_only_when_no_overrides(self):
        tool_config = ToolConfig()
        category_map = _build_hitl_category_map(
            tool_config=tool_config,
            mcp_tool_names=set(),
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={},
        )
        for name, cat in _DEFAULT_CATEGORIES.items():
            assert category_map[name] == cat

    def test_builtin_override_wins_over_default(self):
        tool_config = ToolConfig(
            builtin=BuiltinToolConfig(
                web_search=WebSearchToolConfig(
                    hitl_overrides={"duckduckgo_search": ToolCategory.STATE_MUTATING}
                )
            )
        )
        category_map = _build_hitl_category_map(
            tool_config=tool_config,
            mcp_tool_names=set(),
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={},
        )
        assert category_map["duckduckgo_search"] == ToolCategory.STATE_MUTATING

    def test_mcp_tool_gets_default(self):
        category_map = _build_hitl_category_map(
            tool_config=ToolConfig(),
            mcp_tool_names={"github_search"},
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={},
        )
        assert category_map["github_search"] == ToolCategory.DANGEROUS

    def test_mcp_override_downgrades_dangerous(self):
        category_map = _build_hitl_category_map(
            tool_config=ToolConfig(),
            mcp_tool_names={"github_search"},
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={"github_search": ToolCategory.READ_ONLY},
        )
        assert category_map["github_search"] == ToolCategory.READ_ONLY

    def test_mcp_override_for_unknown_tool_still_applied(self):
        category_map = _build_hitl_category_map(
            tool_config=ToolConfig(),
            mcp_tool_names=set(),
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={"future_mcp_tool": ToolCategory.READ_ONLY},
        )
        assert category_map["future_mcp_tool"] == ToolCategory.READ_ONLY

    def test_mcp_default_overrides_builtin_when_name_collides(self):
        """Spec §4: MCP layer runs after built-ins, so a collision downgrades to mcp_default.

        In practice this means an MCP server that registers a tool named 'read_file'
        will be treated as dangerous (not read_only), because MCP tools' behavior
        is unknown at config time.
        """
        category_map = _build_hitl_category_map(
            tool_config=ToolConfig(),
            mcp_tool_names={"read_file"},  # collides with built-in READ_ONLY
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={},
        )
        assert category_map["read_file"] == ToolCategory.DANGEROUS

    def test_unknown_builtin_override_key_still_recorded(self):
        tool_config = ToolConfig(
            builtin=BuiltinToolConfig(
                filesystem=FilesystemToolConfig(
                    hitl_overrides={"my_new_tool": ToolCategory.STATE_MUTATING}
                )
            )
        )
        category_map = _build_hitl_category_map(
            tool_config=tool_config,
            mcp_tool_names=set(),
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={},
        )
        assert category_map["my_new_tool"] == ToolCategory.STATE_MUTATING
