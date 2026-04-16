# HitL Phase 2: Category-Based Selective Approval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace binary dangerous/safe tool classification with 4-tier category system (read_only/state_mutating/external/dangerous) configured via YAML.

**Architecture:** Add `ToolCategory` enum in shared model, refactor `HitLMiddleware` to accept a pre-built `category_map`, assemble the map in `initialize_async()` from `_DEFAULT_CATEGORIES` + YAML overrides + MCP defaults. Forward `category` through interrupt payload → `_consume_astream` → WebSocket client.

**Tech Stack:** Python 3.13, Pydantic V2, LangGraph interrupt/Command, pytest

---

### Task 1: Add ToolCategory Enum

**Files:**
- Create: `src/models/agent.py`
- Test: `tests/unit/test_hitl_models.py` (existing, extend)

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_hitl_models.py`:

```python
from src.models.agent import ToolCategory


class TestToolCategory:
    """Test ToolCategory enum values and behavior."""

    def test_enum_has_four_categories(self):
        assert len(ToolCategory) == 4

    def test_enum_values(self):
        assert ToolCategory.READ_ONLY == "read_only"
        assert ToolCategory.STATE_MUTATING == "state_mutating"
        assert ToolCategory.EXTERNAL == "external"
        assert ToolCategory.DANGEROUS == "dangerous"

    def test_enum_is_str(self):
        """ToolCategory values can be used as strings (for JSON serialization)."""
        assert isinstance(ToolCategory.READ_ONLY, str)
        assert f"{ToolCategory.DANGEROUS}" == "dangerous"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_models.py::TestToolCategory -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models.agent'`

- [ ] **Step 3: Write minimal implementation**

Create `src/models/agent.py`:

```python
"""Agent-related shared models."""

from enum import StrEnum


class ToolCategory(StrEnum):
    """HitL tool approval category.

    Categories determine whether a tool call requires user approval:
      - READ_ONLY:       auto-execute without approval
      - STATE_MUTATING:  requires approval (file writes, memory changes)
      - EXTERNAL:        requires approval (external system calls)
      - DANGEROUS:       requires approval (shell execution, unclassified tools)
    """

    READ_ONLY = "read_only"
    STATE_MUTATING = "state_mutating"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_models.py::TestToolCategory -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add src/models/agent.py tests/unit/test_hitl_models.py
git commit -m "feat: add ToolCategory enum for HitL category-based approval"
```

---

### Task 2: Add Config Model Fields for HitL Categories

**Files:**
- Modify: `src/configs/agent/openai_chat_agent.py`
- Test: `tests/config/test_agent_config.py` (existing, extend — or create if missing)

- [ ] **Step 1: Write the failing test**

Create or extend `tests/config/test_agent_config.py`:

```python
import pytest
from pydantic import ValidationError

from src.configs.agent.openai_chat_agent import (
    BuiltinToolConfig,
    FilesystemToolConfig,
    HitLConfig,
    ShellToolConfig,
    WebSearchToolConfig,
)
from src.models.agent import ToolCategory


class TestHitLConfigFields:
    """Test HitL category fields on tool config models."""

    def test_filesystem_default_hitl_category(self):
        cfg = FilesystemToolConfig()
        assert cfg.default_hitl_category == ToolCategory.READ_ONLY

    def test_filesystem_default_hitl_overrides(self):
        cfg = FilesystemToolConfig()
        assert cfg.hitl_overrides == {"write_file": ToolCategory.STATE_MUTATING}

    def test_shell_default_hitl_category(self):
        cfg = ShellToolConfig(enabled=True, allowed_commands=["echo"])
        assert cfg.default_hitl_category == ToolCategory.DANGEROUS

    def test_web_search_default_hitl_category(self):
        cfg = WebSearchToolConfig()
        assert cfg.default_hitl_category == ToolCategory.READ_ONLY

    def test_hitl_config_defaults(self):
        cfg = HitLConfig()
        assert cfg.mcp_default_category == ToolCategory.DANGEROUS
        assert cfg.mcp_overrides == {}

    def test_hitl_config_from_yaml_dict(self):
        """Simulate YAML loading with string values — Pydantic coerces to enum."""
        cfg = HitLConfig(
            mcp_default_category="read_only",
            mcp_overrides={"safe_mcp_tool": "read_only"},
        )
        assert cfg.mcp_default_category == ToolCategory.READ_ONLY
        assert cfg.mcp_overrides["safe_mcp_tool"] == ToolCategory.READ_ONLY

    def test_hitl_config_rejects_invalid_category(self):
        with pytest.raises(ValidationError):
            HitLConfig(mcp_default_category="invalid_category")

    def test_tool_config_hitl_overrides_reject_invalid(self):
        with pytest.raises(ValidationError):
            FilesystemToolConfig(hitl_overrides={"read_file": "not_a_category"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/config/test_agent_config.py::TestHitLConfigFields -v`
Expected: FAIL with `ImportError` (no `HitLConfig` or `default_hitl_category` attributes)

- [ ] **Step 3: Write minimal implementation**

Edit `src/configs/agent/openai_chat_agent.py`:

```python
"""OpenAI Chat Agent configuration."""

import os

from pydantic import BaseModel, Field, model_validator

from src.models.agent import ToolCategory


class ShellToolConfig(BaseModel):
    """Configuration for the restricted shell tool."""

    enabled: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    default_hitl_category: ToolCategory = ToolCategory.DANGEROUS
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_commands_if_enabled(self) -> "ShellToolConfig":
        if self.enabled and not self.allowed_commands:
            raise ValueError(
                "shell.enabled=True requires at least one allowed_commands entry"
            )
        return self


class FilesystemToolConfig(BaseModel):
    """Configuration for the filesystem tool."""

    enabled: bool = False
    root_dir: str = "/tmp/agent-workspace"
    default_hitl_category: ToolCategory = ToolCategory.READ_ONLY
    hitl_overrides: dict[str, ToolCategory] = Field(
        default_factory=lambda: {"write_file": ToolCategory.STATE_MUTATING}
    )


class WebSearchToolConfig(BaseModel):
    """Configuration for the web search tool."""

    enabled: bool = False
    default_hitl_category: ToolCategory = ToolCategory.READ_ONLY
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)


class BuiltinToolConfig(BaseModel):
    """Configuration for all builtin tools."""

    filesystem: FilesystemToolConfig = Field(default_factory=FilesystemToolConfig)
    shell: ShellToolConfig = Field(default_factory=ShellToolConfig)
    web_search: WebSearchToolConfig = Field(default_factory=WebSearchToolConfig)


class HitLConfig(BaseModel):
    """HitL category configuration for MCP tools.

    MCP tools are dynamically loaded from external servers.
    Default to dangerous since their behavior is unknown at config time.
    Only override tools that have been verified as safe.
    """

    mcp_default_category: ToolCategory = ToolCategory.DANGEROUS
    mcp_overrides: dict[str, ToolCategory] = Field(default_factory=dict)


class ToolConfig(BaseModel):
    """Top-level tool registry configuration."""

    builtin: BuiltinToolConfig = Field(default_factory=BuiltinToolConfig)


class OpenAIChatAgentConfig(BaseModel):
    """Configuration for OpenAI Chat Agent."""

    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("LLM_API_KEY"),
        description="API key for OpenAI API",
    )
    openai_api_base: str = Field(
        description="Base URL for OpenAI API", default="http://localhost:55120/v1"
    )
    model_name: str = Field(
        description="Name of the OpenAI LLM model",
        default="chat_model",
    )
    top_p: float = Field(0.9, description="Top-p sampling value (for diversity)")
    temperature: float = Field(
        0.7, description="Sampling temperature (controls creativity)"
    )
    mcp_config: dict | None = Field(
        default=None,
        description="MCP client configuration for OpenAI Chat Agent",
    )
    support_image: bool = Field(
        default=False,
        description="Whether the agent supports image inputs in messages",
    )
    tool_config: ToolConfig | None = Field(
        default=None,
        description="Tool registry configuration for builtin tools",
    )
    hitl_config: HitLConfig = Field(
        default_factory=HitLConfig,
        description="HitL category configuration for MCP tools",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/config/test_agent_config.py::TestHitLConfigFields -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Run existing config tests to check no regressions**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/config/ -v`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add src/configs/agent/openai_chat_agent.py tests/config/test_agent_config.py
git commit -m "feat: add HitL category fields to agent config models"
```

---

### Task 3: Refactor HitLMiddleware to Use Category Map

**Files:**
- Modify: `src/services/agent_service/middleware/hitl_middleware.py`
- Modify: `tests/unit/test_hitl_middleware.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/unit/test_hitl_middleware.py` entirely:

```python
"""Unit tests for HitLMiddleware with category-based approval."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.agent import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware


class TestHitLMiddleware:
    """Test HitL middleware category classification and interrupt behavior."""

    def _make_middleware(
        self, category_map: dict[str, ToolCategory] | None = None
    ) -> HitLMiddleware:
        """Create middleware with given category map."""
        return HitLMiddleware(category_map=category_map or {})

    # -- get_category tests --

    def test_read_only_tool_category(self):
        mw = self._make_middleware({"read_file": ToolCategory.READ_ONLY})
        assert mw.get_category("read_file") == ToolCategory.READ_ONLY

    def test_state_mutating_tool_category(self):
        mw = self._make_middleware({"write_file": ToolCategory.STATE_MUTATING})
        assert mw.get_category("write_file") == ToolCategory.STATE_MUTATING

    def test_external_tool_category(self):
        mw = self._make_middleware({"delegate_task": ToolCategory.EXTERNAL})
        assert mw.get_category("delegate_task") == ToolCategory.EXTERNAL

    def test_dangerous_tool_category(self):
        mw = self._make_middleware({"terminal": ToolCategory.DANGEROUS})
        assert mw.get_category("terminal") == ToolCategory.DANGEROUS

    def test_unknown_tool_defaults_to_dangerous(self):
        """Fail-closed: tools not in the map default to DANGEROUS."""
        mw = self._make_middleware({})
        assert mw.get_category("unknown_tool") == ToolCategory.DANGEROUS

    # -- requires_approval tests --

    def test_read_only_does_not_require_approval(self):
        mw = self._make_middleware({"read_file": ToolCategory.READ_ONLY})
        assert not mw.requires_approval("read_file")

    def test_state_mutating_requires_approval(self):
        mw = self._make_middleware({"write_file": ToolCategory.STATE_MUTATING})
        assert mw.requires_approval("write_file")

    def test_external_requires_approval(self):
        mw = self._make_middleware({"delegate_task": ToolCategory.EXTERNAL})
        assert mw.requires_approval("delegate_task")

    def test_dangerous_requires_approval(self):
        mw = self._make_middleware({"terminal": ToolCategory.DANGEROUS})
        assert mw.requires_approval("terminal")

    def test_unknown_tool_requires_approval(self):
        mw = self._make_middleware({})
        assert mw.requires_approval("unknown_tool")

    # -- awrap_tool_call tests --

    @pytest.mark.asyncio
    async def test_read_only_tool_calls_handler_directly(self):
        """read_only tools bypass interrupt and call handler directly."""
        mw = self._make_middleware({"search_memory": ToolCategory.READ_ONLY})
        request = MagicMock()
        request.tool_call = {"name": "search_memory", "args": {"query": "test"}}
        handler = AsyncMock(return_value="search result")

        result = await mw.awrap_tool_call(request, handler)

        handler.assert_awaited_once_with(request)
        assert result == "search result"

    @pytest.mark.asyncio
    async def test_dangerous_tool_triggers_interrupt_with_category(self):
        """Dangerous tools call interrupt() with category in payload."""
        mw = self._make_middleware({"mcp_tool": ToolCategory.DANGEROUS})
        request = MagicMock()
        request.tool_call = {"name": "mcp_tool", "args": {"query": "test"}}
        handler = AsyncMock(return_value="tool result")

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": True, "request_id": "test-123"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            mock_interrupt.assert_called_once()
            call_args = mock_interrupt.call_args[0][0]
            assert call_args["tool_name"] == "mcp_tool"
            assert call_args["tool_args"] == {"query": "test"}
            assert call_args["category"] == "dangerous"
            assert "request_id" in call_args

        handler.assert_awaited_once_with(request)
        assert result == "tool result"

    @pytest.mark.asyncio
    async def test_state_mutating_tool_triggers_interrupt(self):
        """state_mutating tools also trigger interrupt."""
        mw = self._make_middleware({"write_file": ToolCategory.STATE_MUTATING})
        request = MagicMock()
        request.tool_call = {"name": "write_file", "args": {"path": "/tmp/test"}}
        handler = AsyncMock(return_value="written")

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": True, "request_id": "test-456"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            call_args = mock_interrupt.call_args[0][0]
            assert call_args["category"] == "state_mutating"

        handler.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_deny_returns_error_string(self):
        """Denied tools return error string without calling handler."""
        mw = self._make_middleware({"mcp_tool": ToolCategory.DANGEROUS})
        request = MagicMock()
        request.tool_call = {"name": "mcp_tool", "args": {}}
        handler = AsyncMock()

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": False, "request_id": "test-789"},
        ):
            result = await mw.awrap_tool_call(request, handler)

        handler.assert_not_awaited()
        assert "mcp_tool" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_middleware.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'category_map'`

- [ ] **Step 3: Write implementation**

Replace `src/services/agent_service/middleware/hitl_middleware.py`:

```python
"""HitLMiddleware — Human-in-the-Loop approval gate with category-based policy."""

from uuid import uuid4

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.types import interrupt
from loguru import logger

from src.models.agent import ToolCategory

# -- HitL tool approval category defaults --
# Every builtin tool is explicitly mapped here. When adding a new tool,
# add its entry; if omitted, the fail-closed default (DANGEROUS) applies.
_DEFAULT_CATEGORIES: dict[str, ToolCategory] = {
    # Filesystem tools (group: filesystem)
    "read_file": ToolCategory.READ_ONLY,
    "list_directory": ToolCategory.READ_ONLY,
    "write_file": ToolCategory.STATE_MUTATING,
    # Shell tools (group: shell)
    "terminal": ToolCategory.DANGEROUS,
    # Web search tools (group: web_search)
    # Note: YAML group name is "web_search", but actual tool name is "duckduckgo_search"
    "duckduckgo_search": ToolCategory.READ_ONLY,
    # Memory tools
    "add_memory": ToolCategory.STATE_MUTATING,
    "update_memory": ToolCategory.STATE_MUTATING,
    "delete_memory": ToolCategory.STATE_MUTATING,
    "search_memory": ToolCategory.READ_ONLY,
    # Knowledge tools
    "search_knowledge": ToolCategory.READ_ONLY,
    "read_note": ToolCategory.READ_ONLY,
    # Profile tool
    "update_user_profile": ToolCategory.STATE_MUTATING,
    # Delegate tool
    "delegate_task": ToolCategory.EXTERNAL,
}


def build_category_map(
    mcp_tool_names: set[str],
    hitl_overrides: dict[str, ToolCategory] | None = None,
    mcp_default_category: ToolCategory = ToolCategory.DANGEROUS,
    mcp_overrides: dict[str, ToolCategory] | None = None,
) -> dict[str, ToolCategory]:
    """Build the complete tool → category mapping.

    Merge order (later wins):
      1. _DEFAULT_CATEGORIES (all builtin tools)
      2. hitl_overrides (from YAML builtin tool configs)
      3. MCP tools → all set to mcp_default_category
      4. mcp_overrides (from YAML hitl_config)
    """
    category_map: dict[str, ToolCategory] = dict(_DEFAULT_CATEGORIES)

    if hitl_overrides:
        category_map.update(hitl_overrides)

    for name in mcp_tool_names:
        category_map[name] = mcp_default_category

    if mcp_overrides:
        category_map.update(mcp_overrides)

    return category_map


class HitLMiddleware(AgentMiddleware):
    """Intercepts tool calls and requests user approval based on category.

    Categories:
      - READ_ONLY:       bypass (auto-execute)
      - STATE_MUTATING:  requires user approval
      - EXTERNAL:        requires user approval
      - DANGEROUS:       requires user approval (also the default for unknown tools)
    """

    _BYPASS_CATEGORIES: frozenset[ToolCategory] = frozenset({ToolCategory.READ_ONLY})

    def __init__(self, category_map: dict[str, ToolCategory]) -> None:
        self._category_map = category_map

    def get_category(self, tool_name: str) -> ToolCategory:
        """Get the HitL category for a tool. Unknown tools default to DANGEROUS."""
        return self._category_map.get(tool_name, ToolCategory.DANGEROUS)

    def requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval."""
        return self.get_category(tool_name) not in self._BYPASS_CATEGORIES

    async def awrap_tool_call(self, request, handler):
        """Wrap tool call with interrupt() for non-bypass categories."""
        tool_name: str = request.tool_call["name"]

        if not self.requires_approval(tool_name):
            return await handler(request)

        args = request.tool_call.get("args", {})
        request_id = str(uuid4())
        category = self.get_category(tool_name)

        logger.info(
            f"HitL gate: requesting approval for '{tool_name}' "
            f"(category={category.value}, request_id={request_id})"
        )

        resume_value = interrupt(
            {
                "tool_name": tool_name,
                "tool_args": args,
                "request_id": request_id,
                "category": category.value,
            }
        )

        if resume_value.get("approved"):
            logger.info(f"HitL gate: '{tool_name}' approved (request_id={request_id})")
            return await handler(request)

        logger.info(f"HitL gate: '{tool_name}' denied (request_id={request_id})")
        return f"사용자가 '{tool_name}' 도구 실행을 거부했습니다. 다른 방법을 시도해 주세요."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_middleware.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add src/services/agent_service/middleware/hitl_middleware.py tests/unit/test_hitl_middleware.py
git commit -m "feat: refactor HitLMiddleware to use category-based approval"
```

---

### Task 4: Add Category Map Assembly Test

**Files:**
- Create: `tests/unit/test_category_map_assembly.py`

- [ ] **Step 1: Write the tests**

```python
"""Unit tests for build_category_map assembly logic."""

from src.models.agent import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import (
    _DEFAULT_CATEGORIES,
    build_category_map,
)


class TestBuildCategoryMap:
    """Test the category map merge-layer logic."""

    def test_defaults_included(self):
        """All _DEFAULT_CATEGORIES entries are present with no overrides."""
        result = build_category_map(mcp_tool_names=set())
        for name, cat in _DEFAULT_CATEGORIES.items():
            assert result[name] == cat

    def test_hitl_overrides_win_over_defaults(self):
        """YAML hitl_overrides take precedence over _DEFAULT_CATEGORIES."""
        result = build_category_map(
            mcp_tool_names=set(),
            hitl_overrides={"read_file": ToolCategory.STATE_MUTATING},
        )
        assert result["read_file"] == ToolCategory.STATE_MUTATING

    def test_mcp_tools_get_default_category(self):
        """MCP tools not in overrides get mcp_default_category."""
        result = build_category_map(
            mcp_tool_names={"mcp_search", "mcp_write"},
        )
        assert result["mcp_search"] == ToolCategory.DANGEROUS
        assert result["mcp_write"] == ToolCategory.DANGEROUS

    def test_mcp_tools_with_custom_default(self):
        """MCP tools respect a non-DANGEROUS default category."""
        result = build_category_map(
            mcp_tool_names={"mcp_read"},
            mcp_default_category=ToolCategory.READ_ONLY,
        )
        assert result["mcp_read"] == ToolCategory.READ_ONLY

    def test_mcp_overrides_win_over_mcp_default(self):
        """Per-tool MCP overrides take precedence over mcp_default_category."""
        result = build_category_map(
            mcp_tool_names={"mcp_search", "mcp_safe"},
            mcp_default_category=ToolCategory.DANGEROUS,
            mcp_overrides={"mcp_safe": ToolCategory.READ_ONLY},
        )
        assert result["mcp_search"] == ToolCategory.DANGEROUS
        assert result["mcp_safe"] == ToolCategory.READ_ONLY

    def test_full_merge_order(self):
        """Full assembly: defaults → hitl_overrides → MCP defaults → MCP overrides."""
        result = build_category_map(
            mcp_tool_names={"mcp_a", "mcp_b"},
            hitl_overrides={"terminal": ToolCategory.STATE_MUTATING},
            mcp_default_category=ToolCategory.DANGEROUS,
            mcp_overrides={"mcp_b": ToolCategory.EXTERNAL},
        )
        # terminal overridden from DANGEROUS to STATE_MUTATING
        assert result["terminal"] == ToolCategory.STATE_MUTATING
        # mcp_a gets default DANGEROUS
        assert result["mcp_a"] == ToolCategory.DANGEROUS
        # mcp_b overridden to EXTERNAL
        assert result["mcp_b"] == ToolCategory.EXTERNAL
        # read_file untouched from defaults
        assert result["read_file"] == ToolCategory.READ_ONLY

    def test_empty_inputs(self):
        """With no MCP tools and no overrides, result equals _DEFAULT_CATEGORIES."""
        result = build_category_map(mcp_tool_names=set())
        assert result == dict(_DEFAULT_CATEGORIES)
```

- [ ] **Step 2: Run tests (should pass immediately since implementation exists)**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_category_map_assembly.py -v`
Expected: PASS (7 tests)

- [ ] **Step 3: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add tests/unit/test_category_map_assembly.py
git commit -m "test: add category map assembly tests for HitL Phase 2"
```

---

### Task 5: Wire Category Map in Agent Initialization

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py` (constructor + `initialize_async`)
- Modify: `src/services/service_manager.py` (`_inject_extra_config`)
- Create: `tests/unit/test_hitl_agent_init.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_hitl_agent_init.py`:

```python
"""Test that initialize_async builds category_map and passes it to HitLMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.agent import ToolCategory


class TestAgentHitLInit:
    """Test agent initialization wires HitL category map correctly."""

    @pytest.mark.asyncio
    async def test_initialize_builds_category_map(self):
        """HitLMiddleware receives a category_map dict, not raw mcp_tool_names."""
        with (
            patch(
                "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
            ) as MockMCPClient,
            patch(
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
            patch(
                "src.services.agent_service.openai_chat_agent._load_personas",
                return_value={"yuri": "persona text"},
            ),
            patch(
                "src.services.agent_service.openai_chat_agent.get_mongo_client",
                return_value=None,
            ),
            patch(
                "src.services.agent_service.openai_chat_agent.get_user_profile_service",
                return_value=None,
            ),
        ):
            mock_mcp_tool = MagicMock()
            mock_mcp_tool.name = "mcp_test_tool"
            mock_client = AsyncMock()
            mock_client.get_tools = AsyncMock(return_value=[mock_mcp_tool])
            MockMCPClient.return_value = mock_client

            from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

            service = OpenAIChatAgent.__new__(OpenAIChatAgent)
            service.mcp_config = {"test": {}}
            service._mcp_tools = []
            service.tool_config = None
            service.hitl_config = None  # None → uses defaults only
            service.model_name = "test"
            service.llm = MagicMock()

            await service.initialize_async()

            # Verify create_agent was called
            mock_create_agent.assert_called_once()
            middleware_list = mock_create_agent.call_args.kwargs["middleware"]

            # Find HitLMiddleware in the middleware list
            from src.services.agent_service.middleware.hitl_middleware import (
                HitLMiddleware,
            )

            hitl_mw = None
            for mw in middleware_list:
                if isinstance(mw, HitLMiddleware):
                    hitl_mw = mw
                    break

            assert hitl_mw is not None, "HitLMiddleware not found in middleware list"
            # MCP tool should be in the map as DANGEROUS
            assert hitl_mw.get_category("mcp_test_tool") == ToolCategory.DANGEROUS
            # Builtin read_file should be READ_ONLY (from _DEFAULT_CATEGORIES)
            assert hitl_mw.get_category("read_file") == ToolCategory.READ_ONLY

    @pytest.mark.asyncio
    async def test_initialize_with_hitl_config_overrides(self):
        """hitl_config from YAML should override MCP default category."""
        with (
            patch(
                "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
            ) as MockMCPClient,
            patch(
                "src.services.agent_service.openai_chat_agent.create_agent"
            ) as mock_create_agent,
            patch(
                "src.services.agent_service.openai_chat_agent._load_personas",
                return_value={"yuri": "persona text"},
            ),
            patch(
                "src.services.agent_service.openai_chat_agent.get_mongo_client",
                return_value=None,
            ),
            patch(
                "src.services.agent_service.openai_chat_agent.get_user_profile_service",
                return_value=None,
            ),
        ):
            mock_mcp_tool = MagicMock()
            mock_mcp_tool.name = "mcp_safe_tool"
            mock_client = AsyncMock()
            mock_client.get_tools = AsyncMock(return_value=[mock_mcp_tool])
            MockMCPClient.return_value = mock_client

            from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

            service = OpenAIChatAgent.__new__(OpenAIChatAgent)
            service.mcp_config = {"test": {}}
            service._mcp_tools = []
            service.tool_config = None
            service.hitl_config = {
                "mcp_default_category": "dangerous",
                "mcp_overrides": {"mcp_safe_tool": "read_only"},
            }
            service.model_name = "test"
            service.llm = MagicMock()

            await service.initialize_async()

            middleware_list = mock_create_agent.call_args.kwargs["middleware"]

            from src.services.agent_service.middleware.hitl_middleware import (
                HitLMiddleware,
            )

            hitl_mw = next(mw for mw in middleware_list if isinstance(mw, HitLMiddleware))
            # mcp_safe_tool overridden to READ_ONLY
            assert hitl_mw.get_category("mcp_safe_tool") == ToolCategory.READ_ONLY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_agent_init.py -v`
Expected: FAIL — `TypeError` (old `HitLMiddleware(mcp_tool_names=...)` call in `initialize_async`)

- [ ] **Step 3a: Update OpenAIChatAgent.__init__ to accept hitl_config**

In `src/services/agent_service/openai_chat_agent.py`, update the constructor (lines 56-75):

Old:
```python
    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str | None = None,
        openai_api_base: str | None = None,
        model_name: str | None = None,
        tool_config: dict | None = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        self.tool_config = tool_config
        self.agent = None
        self._mcp_tools: list = []
        self._personas: dict[str, str] = {}
        super().__init__(**kwargs)
        logger.info(f"Agent initialized: model={self.model_name}")
```

New:
```python
    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str | None = None,
        openai_api_base: str | None = None,
        model_name: str | None = None,
        tool_config: dict | None = None,
        hitl_config: dict | None = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        self.tool_config = tool_config
        self.hitl_config = hitl_config
        self.agent = None
        self._mcp_tools: list = []
        self._personas: dict[str, str] = {}
        super().__init__(**kwargs)
        logger.info(f"Agent initialized: model={self.model_name}")
```

- [ ] **Step 3b: Update _inject_extra_config in service_manager.py**

In `src/services/service_manager.py`, find `_inject_extra_config` (line 386-388) and add `hitl_config`:

Old:
```python
    def _inject_extra_config(config: dict, service_configs: dict) -> None:
        service_configs["mcp_config"] = config.get("mcp_config")
        service_configs["tool_config"] = config.get("tool_config")
```

New:
```python
    def _inject_extra_config(config: dict, service_configs: dict) -> None:
        service_configs["mcp_config"] = config.get("mcp_config")
        service_configs["tool_config"] = config.get("tool_config")
        service_configs["hitl_config"] = config.get("hitl_config")
```

- [ ] **Step 3c: Update initialize_async() to build category_map**

In `src/services/agent_service/openai_chat_agent.py`, add import at top:
```python
from src.models.agent import ToolCategory
```

Replace lines 163-164:

Old:
```python
        mcp_tool_names = {t.name for t in self._mcp_tools}
        hitl_gate = HitLMiddleware(mcp_tool_names=mcp_tool_names)
```

New:
```python
        from src.services.agent_service.middleware.hitl_middleware import (
            build_category_map,
        )

        # Build HitL category map from defaults + YAML overrides + MCP tools
        mcp_tool_names = {t.name for t in self._mcp_tools}

        # Collect YAML hitl_overrides from builtin tool configs
        hitl_overrides: dict[str, ToolCategory] = {}
        if self.tool_config:
            builtin = self.tool_config.get("builtin", {})
            for _group_name, group_cfg in builtin.items():
                if isinstance(group_cfg, dict) and "hitl_overrides" in group_cfg:
                    for tool_name, cat_str in group_cfg["hitl_overrides"].items():
                        hitl_overrides[tool_name] = ToolCategory(cat_str)

        # MCP HitL config (hitl_config may be None if not in YAML)
        mcp_default_category = ToolCategory.DANGEROUS
        mcp_overrides: dict[str, ToolCategory] = {}
        if self.hitl_config:
            mcp_default_category = ToolCategory(
                self.hitl_config.get("mcp_default_category", "dangerous")
            )
            for tool_name, cat_str in self.hitl_config.get("mcp_overrides", {}).items():
                mcp_overrides[tool_name] = ToolCategory(cat_str)

        category_map = build_category_map(
            mcp_tool_names=mcp_tool_names,
            hitl_overrides=hitl_overrides if hitl_overrides else None,
            mcp_default_category=mcp_default_category,
            mcp_overrides=mcp_overrides if mcp_overrides else None,
        )
        hitl_gate = HitLMiddleware(category_map=category_map)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_agent_init.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run all existing unit tests to check regressions**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add src/services/agent_service/openai_chat_agent.py src/services/service_manager.py tests/unit/test_hitl_agent_init.py
git commit -m "feat: wire category map into agent initialization"
```

---

### Task 6: Forward Category in _consume_astream

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py` (lines 395-401)
- Modify: `tests/unit/test_hitl_agent_stream.py`

- [ ] **Step 1: Update existing mock interrupt data to include `category`**

The existing test helpers `_fake_astream_with_interrupt` (line 24) and `_fake_astream_resume_with_second_interrupt` (line 68) do NOT include `"category"` in their mock interrupt values. After adding `interrupt_value["category"]` to `_consume_astream`, these will raise `KeyError`. Update both:

In `_fake_astream_with_interrupt` (line 24-39), add `"category": "dangerous"` to the value dict:
```python
async def _fake_astream_with_interrupt(*args, **kwargs):
    """Simulate astream that hits an interrupt."""
    yield (
        "updates",
        {
            "__interrupt__": [
                MagicMock(
                    value={
                        "tool_name": "mcp_search",
                        "tool_args": {"query": "test"},
                        "request_id": "req-123",
                        "category": "dangerous",
                    }
                )
            ]
        },
    )
```

In `_fake_astream_resume_with_second_interrupt` (line 68-89), add `"category": "dangerous"` to the value dict:
```python
async def _fake_astream_resume_with_second_interrupt(*args, **kwargs):
    """Simulate resumed astream that hits another interrupt."""
    yield (
        "updates",
        {
            "tools": {"messages": [MagicMock(content="First tool done")]},
        },
    )
    yield (
        "updates",
        {
            "__interrupt__": [
                MagicMock(
                    value={
                        "tool_name": "mcp_write",
                        "tool_args": {"data": "important"},
                        "request_id": "req-456",
                        "category": "dangerous",
                    }
                )
            ]
        },
    )
```

- [ ] **Step 2: Write the new category test**

Add to `tests/unit/test_hitl_agent_stream.py`:

```python
class TestHitLRequestCategory:
    """Test that hitl_request events include category field."""

    @pytest.mark.asyncio
    async def test_hitl_request_includes_category(self):
        """_consume_astream should include category from interrupt payload."""
        agent = _make_agent()
        agent.agent.astream = _fake_astream_with_interrupt

        events = []
        async for event in agent._consume_astream(
            agent.agent.astream(), "session-1"
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == "hitl_request"
        assert events[0]["category"] == "dangerous"
        assert events[0]["tool_name"] == "mcp_search"
        assert events[0]["session_id"] == "session-1"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_agent_stream.py -v`
Expected: FAIL — `KeyError: 'category'` in `_consume_astream`

- [ ] **Step 4: Update _consume_astream**

In `src/services/agent_service/openai_chat_agent.py`, replace lines 395-401:

Old:
```python
                        yield {
                            "type": "hitl_request",
                            "request_id": interrupt_value["request_id"],
                            "tool_name": interrupt_value["tool_name"],
                            "tool_args": interrupt_value["tool_args"],
                            "session_id": session_id,
                        }
```

New:
```python
                        yield {
                            "type": "hitl_request",
                            "request_id": interrupt_value["request_id"],
                            "tool_name": interrupt_value["tool_name"],
                            "tool_args": interrupt_value["tool_args"],
                            "session_id": session_id,
                            "category": interrupt_value["category"],
                        }
```

- [ ] **Step 5: Run all hitl stream tests to verify they pass**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_agent_stream.py -v`
Expected: All PASS (existing tests pass because mocks now include `category`, new test passes because `_consume_astream` forwards it)

- [ ] **Step 6: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add src/services/agent_service/openai_chat_agent.py tests/unit/test_hitl_agent_stream.py
git commit -m "feat: forward category field in hitl_request events"
```

---

### Task 7: Update HitLRequestMessage Model

**Files:**
- Modify: `src/models/websocket.py` (lines 220-228)
- Modify: `tests/unit/test_hitl_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_hitl_models.py`:

```python
class TestHitLRequestMessageCategory:
    """Test HitLRequestMessage includes category field."""

    def test_hitl_request_has_category_field(self):
        msg = HitLRequestMessage(
            request_id="req-1",
            tool_name="mcp_tool",
            tool_args={"key": "val"},
            session_id="sess-1",
            category="dangerous",
        )
        assert msg.category == "dangerous"

    def test_hitl_request_serialization_includes_category(self):
        msg = HitLRequestMessage(
            request_id="req-1",
            tool_name="mcp_tool",
            tool_args={},
            session_id="sess-1",
            category="state_mutating",
        )
        data = msg.model_dump()
        assert data["category"] == "state_mutating"

    def test_hitl_request_rejects_invalid_category(self):
        """Invalid category string should be rejected by validation."""
        with pytest.raises(ValidationError):
            HitLRequestMessage(
                request_id="req-1",
                tool_name="tool",
                tool_args={},
                session_id="sess-1",
                category="invalid",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_models.py::TestHitLRequestMessageCategory -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'category'`

- [ ] **Step 3: Update HitLRequestMessage**

In `src/models/websocket.py`, add import and modify `HitLRequestMessage`:

```python
from src.models.agent import ToolCategory

class HitLRequestMessage(BaseMessage):
    """Server message requesting user approval for a tool call."""

    type: MessageType = MessageType.HITL_REQUEST
    request_id: str = Field(..., description="Unique ID linking request/response")
    tool_name: str = Field(..., description="Name of the tool requiring approval")
    tool_args: dict[str, Any] = Field(..., description="Tool call arguments")
    session_id: str = Field(..., description="Session ID for graph resume")
    category: ToolCategory = Field(
        ..., description="Tool category: read_only, state_mutating, external, dangerous"
    )
```

- [ ] **Step 4: Update existing HitLRequestMessage tests**

Since `category` is now a required field, all existing `HitLRequestMessage(...)` constructions in `tests/unit/test_hitl_models.py` will fail. Add `category="dangerous"` to every existing `HitLRequestMessage(...)` call in the file. For example, existing tests like `test_hitl_request_message_type` and `test_hitl_request_serialization` need the field added.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && uv run pytest tests/unit/test_hitl_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add src/models/websocket.py tests/unit/test_hitl_models.py
git commit -m "feat: add category field to HitLRequestMessage"
```

---

### Task 8: Update YAML Config Files

**Files:**
- Modify: `yaml_files/services.yml`
- Modify: `yaml_files/services.e2e.yml`
- Modify: `yaml_files/services.docker.yml` (if exists)

- [ ] **Step 1: Add HitL comments and hitl_config section**

Add to the `agent` section of each YAML file (after the existing `tool_config` block):

```yaml
    # -- HitL (Human-in-the-Loop) tool approval policy --
    # Category behavior:
    #   read_only       -> auto-execute without approval
    #   state_mutating  -> requires approval (file writes, memory changes)
    #   external        -> requires approval (external system calls)
    #   dangerous       -> requires approval (shell execution, unclassified tools)
    #
    # Builtin tool categories are defined in _DEFAULT_CATEGORIES (hitl_middleware.py).
    # YAML hitl_overrides can override individual tool categories per group.
    # Tools not in any mapping default to dangerous (fail-closed).
    hitl_config:
      mcp_default_category: dangerous
      mcp_overrides: {}
```

- [ ] **Step 2: Verify YAML is valid**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && python -c "import yaml; yaml.safe_load(open('yaml_files/services.yml')); print('OK')" && python -c "import yaml; yaml.safe_load(open('yaml_files/services.e2e.yml')); print('OK')"`
Expected: Both print "OK"

- [ ] **Step 3: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add yaml_files/
git commit -m "feat: add hitl_config section to YAML service configs"
```

---

### Task 9: Run Full Unit Test Suite + Lint

**Files:** None (verification only)

- [ ] **Step 1: Run lint**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && make lint`
Expected: PASS (fix any issues if they arise)

- [ ] **Step 2: Run full unit test suite**

Run: `cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2 && make test`
Expected: All PASS

- [ ] **Step 3: Fix any failures, commit fixes**

If any test fails, fix and commit:
```bash
git add -A && git commit -m "fix: resolve test/lint issues from HitL Phase 2"
```

---

### Task 10: Update E2E Tests for Category Field

**Files:**
- Modify: `tests/e2e/test_hitl_e2e.py`

- [ ] **Step 1: Update schema validation test**

In `TestHitLApproveFlow.test_hitl_request_has_correct_schema`, add category assertion after the existing field checks (around line 330-334):

```python
            # Validate category field (Phase 2)
            assert "category" in hitl_event, "hitl_request must include category field"
            assert hitl_event["category"] in (
                "read_only",
                "state_mutating",
                "external",
                "dangerous",
            ), f"Invalid category: {hitl_event['category']}"
```

- [ ] **Step 2: Commit**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
git add tests/e2e/test_hitl_e2e.py
git commit -m "test: add category field validation to HitL E2E tests"
```

---

### Task 11: Run E2E Tests

**Files:** None (verification only)

- [ ] **Step 1: Start the backend**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
YAML_FILE=yaml_files/services.e2e.yml uv run uvicorn "src.main:get_app" --factory --port 7123 &
```

Wait for server to be ready.

- [ ] **Step 2: Run E2E tests**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_hitl_e2e.py --tb=long -v
```

Expected: All PASS (some may skip due to non-deterministic LLM behavior — that's OK)

- [ ] **Step 3: Stop the backend and fix any failures**

```bash
kill %1  # stop background uvicorn
```

If failures: fix, commit, re-run.

- [ ] **Step 4: Run full E2E suite**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
bash scripts/e2e.sh
```

Expected: All PASS
