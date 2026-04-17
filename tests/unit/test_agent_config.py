"""Unit tests for OpenAI Chat Agent config models — HitL fields + extra=forbid."""

import pytest
from pydantic import ValidationError

from src.configs.agent.openai_chat_agent import (
    FilesystemToolConfig,
    OpenAIChatAgentConfig,
    ShellToolConfig,
    WebSearchToolConfig,
)
from src.models.websocket import ToolCategory


class TestToolConfigHitLFields:
    def test_filesystem_defaults_to_empty_overrides(self):
        cfg = FilesystemToolConfig()
        assert cfg.hitl_overrides == {}

    def test_filesystem_accepts_override(self):
        cfg = FilesystemToolConfig(
            hitl_overrides={"write_file": ToolCategory.STATE_MUTATING}
        )
        assert cfg.hitl_overrides == {"write_file": ToolCategory.STATE_MUTATING}

    def test_filesystem_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            FilesystemToolConfig.model_validate({"default_hitl_category": "read_only"})

    def test_shell_rejects_bad_category_value(self):
        with pytest.raises(ValidationError):
            ShellToolConfig.model_validate(
                {"hitl_overrides": {"terminal": "not_a_category"}}
            )

    def test_shell_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            ShellToolConfig.model_validate({"default_hitl_category": "dangerous"})

    def test_web_search_defaults_empty(self):
        assert WebSearchToolConfig().hitl_overrides == {}

    def test_web_search_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            WebSearchToolConfig.model_validate({"default_hitl_category": "read_only"})


class TestAgentConfigMCPHitL:
    def test_mcp_default_is_dangerous(self):
        cfg = OpenAIChatAgentConfig()
        assert cfg.mcp_default_hitl_category == ToolCategory.DANGEROUS
        assert cfg.mcp_hitl_overrides == {}

    def test_mcp_overrides_validated(self):
        with pytest.raises(ValidationError):
            OpenAIChatAgentConfig.model_validate(
                {"mcp_hitl_overrides": {"foo": "readonly"}}
            )

    def test_agent_config_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            OpenAIChatAgentConfig.model_validate({"nonexistent_field": True})
