# HitL Phase 2: Category-Based Selective Approval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `HitLMiddleware`'s binary dangerous/safe classification with a 4-tier category system (`read_only` / `state_mutating` / `external` / `dangerous`) driven by a code-authoritative catalog and YAML overrides, emitting `category` on every interrupt payload so future policy extensions can key off it.

**Architecture:** A `ToolCategory` enum lives in `src/models/websocket.py` (alongside `HitLRequestMessage`). A `_DEFAULT_CATEGORIES` constant in `hitl_middleware.py` maps every built-in tool name → category. `OpenAIChatAgent.initialize_async()` merges `_DEFAULT_CATEGORIES` + validated `tool_config.builtin.*.hitl_overrides` + runtime MCP tool names (classified by `mcp_default_hitl_category`, layered with `mcp_hitl_overrides`) into a `category_map: dict[str, ToolCategory]` passed to `HitLMiddleware`. The middleware bypasses `read_only`, interrupts on everything else, and forwards the category string into the interrupt payload. Fail-closed: any tool absent from the map defaults to `dangerous`.

**Tech Stack:** Python 3.13, FastAPI, LangChain/LangGraph, Pydantic V2, Pytest, loguru. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-17-hitl-phase2-category-approval-design.md`

**Issue:** #42

---

## File Structure

### Create
- `tests/unit/test_category_map_assembly.py` — unit tests for the `_build_hitl_category_map` helper
- `tests/structural/test_default_categories_coverage.py` — structural test asserting every built-in tool name is registered in `_DEFAULT_CATEGORIES`

### Modify
- `src/models/websocket.py` — add `ToolCategory` enum + `category` field on `HitLRequestMessage`
- `src/configs/agent/openai_chat_agent.py` — add `hitl_overrides` to the three tool configs and `mcp_default_hitl_category` / `mcp_hitl_overrides` to `OpenAIChatAgentConfig`; add `ConfigDict(extra="forbid")` to all four
- `src/services/agent_service/middleware/hitl_middleware.py` — replace `is_dangerous`/deny-list with `_DEFAULT_CATEGORIES` + `get_category` + `requires_approval`, include `category` in interrupt payload, accept `category_map` in constructor
- `src/services/agent_service/openai_chat_agent.py` — validate `tool_config` dict → `ToolConfig` in `__init__`; add `_build_hitl_category_map` helper; pass `category_map` to `HitLMiddleware(...)` in `initialize_async`; forward `category` in `_consume_astream`
- `tests/unit/test_hitl_middleware.py` — rewrite to the new API (`get_category` / `requires_approval` + category payload)
- `tests/unit/test_hitl_models.py` — assert `category` field on `HitLRequestMessage`
- `tests/unit/test_hitl_agent_stream.py` — assert `_consume_astream` forwards `category`
- `tests/e2e/test_hitl_e2e.py` — assert `hitl_request` event includes `category`; add a `read_only` bypass case
- `docs/data_flow/agent/HITL_GATE_FLOW.md` — replace Phase 1 binary classifier with 4-tier categories; add `category` to interrupt payload + JSON schema; PatchNote
- `docs/data_flow/chat/ADD_CHAT_MESSAGE.md` — update HitL Gate section, mermaid notes, related-docs link
- `docs/data_flow/chat/CONTEXT_INJECTION_FLOW.md` — update HitLMiddleware description

### No Changes
- `HitLResponseMessage`, WebSocket routing, `handle_hitl_response()`, `resume_after_approval()` — all stay as-is (see spec §7)

---

## Pre-flight (do once before Task 1)

- [ ] **Verify worktree and branch**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
git worktree list
```

Expected: a worktree at `backend/worktrees/hitl-phase2` on branch `feat/hitl-phase2-category-approval`. If the worktree exists but the spec inside it is outdated, sync:

```bash
cp docs/superpowers/specs/2026-04-17-hitl-phase2-category-approval-design.md \
   worktrees/hitl-phase2/docs/superpowers/specs/2026-04-17-hitl-phase2-category-approval-design.md
cp docs/superpowers/plans/2026-04-17-hitl-phase2-category-approval.md \
   worktrees/hitl-phase2/docs/superpowers/plans/2026-04-17-hitl-phase2-category-approval.md
cd worktrees/hitl-phase2
git add docs/ && git commit -m "docs: sync Phase 2 spec and plan"
```

All subsequent tasks run from the worktree:

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend/worktrees/hitl-phase2
```

- [ ] **Scan for alien YAML keys (migration pre-check)**

```bash
grep -rn "default_hitl_category:" yaml_files/ ; \
grep -rn "builtin_tools:" yaml_files/
```

Expected: no hits. The real YAML schema is `tool_config.builtin.*` (verified against `yaml_files/services.yml`), so `builtin_tools:` should never appear — any hit is truly stale from an early spec draft and should be deleted. If you find a hit and are unsure whether it's intentional, stop and check `yaml_files/services*.yml` structure before editing. These must be cleaned up before Task 2's `extra="forbid"` change, otherwise every environment will fail startup.

- [ ] **Confirm tests pass on base branch**

```bash
uv run pytest tests/unit/test_hitl_middleware.py tests/unit/test_hitl_models.py tests/unit/test_hitl_agent_stream.py -v
```

Expected: all green (Phase 1 behavior). Write this baseline down — some tests must fail after Task 3 before being rewritten in Task 8.

---

### Task 1: Add `ToolCategory` enum and extend `HitLRequestMessage`

**Files:**
- Modify: `src/models/websocket.py`
- Test: `tests/unit/test_hitl_models.py`

This lands the shared type first so downstream tasks can import it. `ToolCategory` lives in the same module as `HitLRequestMessage` to keep the interrupt-payload schema co-located (spec §1, §5). `src/models/websocket.py` must remain a leaf module — no imports from `services/` or `configs/`.

- [ ] **Step 0: Enumerate existing `HitLRequestMessage` call sites**

Before writing new tests, find every existing instantiation so Step 5 can fix them in one pass:

```bash
grep -rn "HitLRequestMessage(" tests/ src/ | grep -v "class HitLRequestMessage"
```

Record the file:line list. Each hit that omits `category=` must be updated in Step 5.

- [ ] **Step 1: Write the failing test**

Edit `tests/unit/test_hitl_models.py`. Add these test methods to the existing test class (or create `TestHitLRequestMessage` if absent):

```python
import pytest
from pydantic import ValidationError

from src.models.websocket import HitLRequestMessage, MessageType, ToolCategory


class TestToolCategoryEnum:
    def test_enum_values_are_strings(self):
        assert ToolCategory.READ_ONLY.value == "read_only"
        assert ToolCategory.STATE_MUTATING.value == "state_mutating"
        assert ToolCategory.EXTERNAL.value == "external"
        assert ToolCategory.DANGEROUS.value == "dangerous"

    def test_enum_is_str_subclass(self):
        # allows wire-format comparisons like `category == "read_only"`
        assert isinstance(ToolCategory.READ_ONLY, str)


class TestHitLRequestMessageCategory:
    def test_category_field_required(self):
        with pytest.raises(ValidationError):
            HitLRequestMessage(
                request_id="r1",
                tool_name="write_file",
                tool_args={},
                session_id="s1",
            )

    def test_category_accepts_enum(self):
        msg = HitLRequestMessage(
            request_id="r1",
            tool_name="write_file",
            tool_args={},
            session_id="s1",
            category=ToolCategory.STATE_MUTATING,
        )
        assert msg.type == MessageType.HITL_REQUEST
        assert msg.category == ToolCategory.STATE_MUTATING

    def test_category_coerces_from_string(self):
        # wire format is a string (see spec §6 "Wire format is string, not enum")
        msg = HitLRequestMessage(
            request_id="r1",
            tool_name="terminal",
            tool_args={},
            session_id="s1",
            category="dangerous",
        )
        assert msg.category == ToolCategory.DANGEROUS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_hitl_models.py::TestToolCategoryEnum -v
```

Expected: `ImportError` or `AttributeError` — `ToolCategory` does not exist yet.

- [ ] **Step 3: Add `ToolCategory` enum to `src/models/websocket.py`**

Find the top of the file (imports and `MessageType`). Add `ToolCategory` immediately after `MessageType`:

```python
class ToolCategory(StrEnum):
    """HitL classification that determines whether a tool call requires approval.

    See docs/superpowers/specs/2026-04-17-hitl-phase2-category-approval-design.md.
    """

    READ_ONLY = "read_only"
    STATE_MUTATING = "state_mutating"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"
```

`StrEnum` is already imported at the top of the file (`from enum import StrEnum`).

- [ ] **Step 4: Add `category` field to `HitLRequestMessage`**

Find `class HitLRequestMessage(BaseMessage):` (around line 220). Add the new field as the last member:

```python
class HitLRequestMessage(BaseMessage):
    """Server message requesting user approval for a tool call."""

    type: MessageType = MessageType.HITL_REQUEST
    request_id: str = Field(..., description="Unique ID linking request/response")
    tool_name: str = Field(..., description="Name of the tool requiring approval")
    tool_args: dict[str, Any] = Field(..., description="Tool call arguments")
    session_id: str = Field(..., description="Session ID for graph resume")
    category: ToolCategory = Field(
        ...,
        description="HitL category of the tool (drives UI copy, future batch-approval policy)",
    )
```

Note: the Pydantic model is schema-only today — the live WebSocket pipeline yields a raw dict (see Task 6). Keeping the model in sync prevents silent drift.

- [ ] **Step 5: Run tests — should pass**

```bash
uv run pytest tests/unit/test_hitl_models.py -v
```

Expected: all tests in `TestToolCategoryEnum` and `TestHitLRequestMessageCategory` pass. Any older test in the same file that constructs `HitLRequestMessage` without `category=...` will now fail — fix those at the call sites by adding `category=ToolCategory.DANGEROUS` (sensible default for legacy fixtures; this is a test file only).

- [ ] **Step 6: Run the full model test file and lint**

```bash
uv run pytest tests/unit/test_hitl_models.py -v
uv run ruff check src/models/websocket.py tests/unit/test_hitl_models.py
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/models/websocket.py tests/unit/test_hitl_models.py
git commit -m "feat: add ToolCategory enum and category field on HitLRequestMessage"
```

---

### Task 2: Extend config models with HitL fields + `extra="forbid"`

**Files:**
- Modify: `src/configs/agent/openai_chat_agent.py`
- Test: `tests/unit/test_agent_config.py` (create if it does not exist; if a file with a different name already covers this config, add tests there instead — check `tests/config/` and `tests/agents/`)

Add per-tool `hitl_overrides` to `FilesystemToolConfig` / `ShellToolConfig` / `WebSearchToolConfig`, add `mcp_default_hitl_category` / `mcp_hitl_overrides` to `OpenAIChatAgentConfig`, and add `ConfigDict(extra="forbid")` to all four so stale YAML keys fail at startup (spec §2).

- [ ] **Step 1: Locate the right test file**

```bash
grep -rn "OpenAIChatAgentConfig\|FilesystemToolConfig" tests/ | head
```

If no test file exercises these models directly, create `tests/unit/test_agent_config.py`. Otherwise append the new tests to the existing file.

- [ ] **Step 2: Write the failing tests**

In the target test file:

```python
import pytest
from pydantic import ValidationError

from src.configs.agent.openai_chat_agent import (
    FilesystemToolConfig,
    ShellToolConfig,
    WebSearchToolConfig,
    OpenAIChatAgentConfig,
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
            FilesystemToolConfig(default_hitl_category="read_only")  # type: ignore[call-arg]

    def test_shell_rejects_bad_category_value(self):
        with pytest.raises(ValidationError):
            ShellToolConfig(hitl_overrides={"terminal": "not_a_category"})  # type: ignore[arg-type]

    def test_web_search_defaults_empty(self):
        assert WebSearchToolConfig().hitl_overrides == {}


class TestAgentConfigMCPHitL:
    def test_mcp_default_is_dangerous(self):
        cfg = OpenAIChatAgentConfig()
        assert cfg.mcp_default_hitl_category == ToolCategory.DANGEROUS
        assert cfg.mcp_hitl_overrides == {}

    def test_mcp_overrides_validated(self):
        with pytest.raises(ValidationError):
            OpenAIChatAgentConfig(mcp_hitl_overrides={"foo": "readonly"})  # type: ignore[arg-type]

    def test_agent_config_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            OpenAIChatAgentConfig(nonexistent_field=True)  # type: ignore[call-arg]
```

- [ ] **Step 3: Run tests to verify failure**

```bash
uv run pytest tests/unit/test_agent_config.py -v
```

Expected: tests fail because the fields and `extra="forbid"` do not exist yet.

- [ ] **Step 4: Add `ConfigDict(extra="forbid")` + `hitl_overrides` to the three tool configs**

Edit `src/configs/agent/openai_chat_agent.py`. Update imports at the top:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.websocket import ToolCategory
```

Update the three tool configs (keep existing fields; add `model_config` and `hitl_overrides`):

```python
class ShellToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_commands_if_enabled(self) -> "ShellToolConfig":
        if self.enabled and not self.allowed_commands:
            raise ValueError(
                "shell.enabled=True requires at least one allowed_commands entry"
            )
        return self


class FilesystemToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    root_dir: str = "/tmp/agent-workspace"
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)


class WebSearchToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)
```

- [ ] **Step 5: Add MCP HitL fields + `extra="forbid"` to `OpenAIChatAgentConfig`**

Locate `class OpenAIChatAgentConfig(BaseModel):` (around line 50) and add `model_config` at the top of the class plus the two new fields at the bottom (next to the existing `tool_config`):

```python
class OpenAIChatAgentConfig(BaseModel):
    """Configuration for OpenAI Chat Agent."""

    model_config = ConfigDict(extra="forbid")

    # ... existing fields unchanged (openai_api_key, model_name, top_p, temperature,
    #     mcp_config, support_image, tool_config, ...) ...

    mcp_default_hitl_category: ToolCategory = Field(
        default=ToolCategory.DANGEROUS,
        description="HitL category applied to every discovered MCP tool unless overridden",
    )
    mcp_hitl_overrides: dict[str, ToolCategory] = Field(
        default_factory=dict,
        description="Per-MCP-tool category overrides (verified-safe tools get downgraded)",
    )
```

- [ ] **Step 6: Verify every environment YAML still loads**

Check all three environment files. Alien keys in `services.docker.yml` or `services.e2e.yml` must fail now (local) rather than at deploy time:

```bash
uv run python - <<'PY'
import sys, yaml
from src.configs.agent.openai_chat_agent import OpenAIChatAgentConfig, ToolConfig

files = [
    "yaml_files/services.yml",
    "yaml_files/services.docker.yml",
    "yaml_files/services.e2e.yml",
]
failed = []
for path in files:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        # OpenAIChatAgentConfig fields live under llm_config.configs (verified against services.yml)
        llm_configs = (data.get("llm_config") or {}).get("configs") or {}
        OpenAIChatAgentConfig(**llm_configs)
        # tool_config is injected as a top-level YAML key via _inject_extra_config
        tc = data.get("tool_config")
        if tc:
            ToolConfig.model_validate(tc)
        print(f"  OK: {path}")
    except Exception as e:
        print(f"  FAIL: {path} — {e}", file=sys.stderr)
        failed.append(path)
sys.exit(1 if failed else 0)
PY
```

Expected: three `OK:` lines and exit 0. If any file fails with `ValidationError` for unknown keys, stop and clean the alien key from that specific YAML. Only after all three pass proceed to Step 7. If the alien key is legitimately required by some other consumer and cannot be removed, fall back to the narrow validator approach described in spec §2 last paragraph instead of `extra="forbid"`.

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/unit/test_agent_config.py -v
```

Expected: all new tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/configs/agent/openai_chat_agent.py tests/unit/test_agent_config.py
git commit -m "feat: add hitl_overrides + extra=forbid to agent config models"
```

---

### Task 3: Refactor `HitLMiddleware` to use a category map

**Files:**
- Modify: `src/services/agent_service/middleware/hitl_middleware.py`
- Test: `tests/unit/test_hitl_middleware.py` (rewrite)

Replace the boolean `is_dangerous` with `get_category` + `requires_approval`. Accept a pre-built `category_map` in the constructor (spec §3). The existing test file will be rewritten because the old `is_dangerous` API goes away.

- [ ] **Step 1: Rewrite `tests/unit/test_hitl_middleware.py`**

Replace the entire file with the new API-driven tests:

```python
"""Unit tests for HitLMiddleware (Phase 2 — category-based)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.websocket import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware


class TestHitLMiddlewareCategory:
    def _mw(self, category_map: dict[str, ToolCategory] | None = None) -> HitLMiddleware:
        return HitLMiddleware(category_map=category_map or {})

    def test_get_category_returns_mapped(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        assert mw.get_category("read_file") == ToolCategory.READ_ONLY

    def test_get_category_unknown_is_dangerous(self):
        # fail-closed default
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        assert mw.get_category("ghost_tool") == ToolCategory.DANGEROUS

    def test_requires_approval_bypasses_read_only(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        assert mw.requires_approval("read_file") is False

    @pytest.mark.parametrize(
        "cat", [ToolCategory.STATE_MUTATING, ToolCategory.EXTERNAL, ToolCategory.DANGEROUS]
    )
    def test_requires_approval_true_for_non_bypass(self, cat: ToolCategory):
        mw = self._mw({"t": cat})
        assert mw.requires_approval("t") is True


class TestHitLMiddlewareInterrupt:
    def _mw(self, category_map: dict[str, ToolCategory]) -> HitLMiddleware:
        return HitLMiddleware(category_map=category_map)

    @pytest.mark.asyncio
    async def test_read_only_tool_calls_handler_without_interrupt(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})
        request = MagicMock()
        request.tool_call = {"name": "read_file", "args": {"path": "/tmp/x"}}
        handler = AsyncMock(return_value="contents")

        result = await mw.awrap_tool_call(request, handler)

        handler.assert_awaited_once_with(request)
        assert result == "contents"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "category",
        [ToolCategory.STATE_MUTATING, ToolCategory.EXTERNAL, ToolCategory.DANGEROUS],
    )
    async def test_non_bypass_category_interrupts_with_category_payload(
        self, category: ToolCategory
    ):
        mw = self._mw({"write_file": category})
        request = MagicMock()
        request.tool_call = {"name": "write_file", "args": {"path": "/tmp/x"}}
        handler = AsyncMock(return_value="ok")

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": True, "request_id": "r-1"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            call_payload = mock_interrupt.call_args[0][0]
            assert call_payload["tool_name"] == "write_file"
            assert call_payload["tool_args"] == {"path": "/tmp/x"}
            assert call_payload["category"] == category.value  # str wire format
            assert "request_id" in call_payload

        handler.assert_awaited_once_with(request)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unknown_tool_treated_as_dangerous(self):
        mw = self._mw({"read_file": ToolCategory.READ_ONLY})  # ghost_tool absent
        request = MagicMock()
        request.tool_call = {"name": "ghost_tool", "args": {}}
        handler = AsyncMock()

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": False, "request_id": "r-2"},
        ) as mock_interrupt:
            result = await mw.awrap_tool_call(request, handler)

            assert mock_interrupt.call_args[0][0]["category"] == ToolCategory.DANGEROUS.value

        handler.assert_not_awaited()
        assert "ghost_tool" in result.lower() or "거부" in result

    @pytest.mark.asyncio
    async def test_denied_returns_error_string_without_handler(self):
        mw = self._mw({"write_file": ToolCategory.STATE_MUTATING})
        request = MagicMock()
        request.tool_call = {"name": "write_file", "args": {}}
        handler = AsyncMock()

        with patch(
            "src.services.agent_service.middleware.hitl_middleware.interrupt",
            return_value={"approved": False, "request_id": "r-3"},
        ):
            result = await mw.awrap_tool_call(request, handler)

        handler.assert_not_awaited()
        assert isinstance(result, str)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/unit/test_hitl_middleware.py -v
```

Expected: failures — old `HitLMiddleware(mcp_tool_names=...)` signature does not accept `category_map`.

- [ ] **Step 3: Rewrite `src/services/agent_service/middleware/hitl_middleware.py`**

Replace the whole file with:

```python
"""HitLMiddleware — Human-in-the-Loop approval gate driven by a category map."""

from uuid import uuid4

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.types import interrupt
from loguru import logger

from src.models.websocket import ToolCategory

# Single source of truth for built-in tool categories.
# When adding a new built-in tool, add an entry here. A missing entry falls back
# to `ToolCategory.DANGEROUS` at lookup time (fail-closed). The structural test
# `tests/structural/test_default_categories_coverage.py` enforces completeness.
_DEFAULT_CATEGORIES: dict[str, ToolCategory] = {
    # Filesystem tools (group: filesystem)
    "read_file": ToolCategory.READ_ONLY,
    "list_directory": ToolCategory.READ_ONLY,
    "write_file": ToolCategory.STATE_MUTATING,
    # Shell tools (group: shell)
    "terminal": ToolCategory.DANGEROUS,
    # Web search (group: web_search — actual tool name is "duckduckgo_search")
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


class HitLMiddleware(AgentMiddleware):
    """Intercepts non-bypass tool calls and requests user approval via interrupt().

    Bypass categories execute without approval. All other categories interrupt
    with the category forwarded in the payload so the client can differentiate
    UX (warning color, copy, future batch-approval policy).
    """

    _BYPASS_CATEGORIES: frozenset[ToolCategory] = frozenset({ToolCategory.READ_ONLY})

    def __init__(self, category_map: dict[str, ToolCategory]) -> None:
        self._category_map = dict(category_map)

    def get_category(self, tool_name: str) -> ToolCategory:
        """Look up the category for a tool. Unknown tools are fail-closed `dangerous`."""
        return self._category_map.get(tool_name, ToolCategory.DANGEROUS)

    def requires_approval(self, tool_name: str) -> bool:
        return self.get_category(tool_name) not in self._BYPASS_CATEGORIES

    async def awrap_tool_call(self, request, handler):
        tool_name: str = request.tool_call["name"]
        category = self.get_category(tool_name)

        if category in self._BYPASS_CATEGORIES:
            logger.info(
                f"HitL gate: '{tool_name}' bypass (category={category.value})"
            )
            return await handler(request)

        args = request.tool_call.get("args", {})
        request_id = str(uuid4())

        logger.info(
            f"HitL gate: requesting approval for '{tool_name}' "
            f"(category={category.value}, request_id={request_id})"
        )

        resume_value = interrupt(
            {
                "tool_name": tool_name,
                "tool_args": args,
                "request_id": request_id,
                "category": category.value,  # wire format: string, not enum
            }
        )

        if resume_value.get("approved"):
            logger.info(
                f"HitL gate: '{tool_name}' approved "
                f"(category={category.value}, request_id={request_id})"
            )
            return await handler(request)

        logger.info(
            f"HitL gate: '{tool_name}' denied "
            f"(category={category.value}, request_id={request_id})"
        )
        return f"사용자가 '{tool_name}' 도구 실행을 거부했습니다. 다른 방법을 시도해 주세요."
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_hitl_middleware.py -v
```

Expected: all new tests green. If `import` errors elsewhere (e.g., `openai_chat_agent.py` still passes `mcp_tool_names=...`), leave them — Task 4 fixes the call site.

- [ ] **Step 5: Commit**

```bash
git add src/services/agent_service/middleware/hitl_middleware.py tests/unit/test_hitl_middleware.py
git commit -m "refactor: HitLMiddleware uses category_map with fail-closed default"
```

---

### Task 4: Wire `category_map` into `OpenAIChatAgent.initialize_async()`

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py`
- Test: `tests/unit/test_category_map_assembly.py` (new)

Validate the injected `tool_config` dict → `ToolConfig` in `__init__`, build `category_map` via a module-level helper, and hand it to `HitLMiddleware` (spec §2, §4). This task also fixes the call site that Task 3 left broken.

- [ ] **Step 1: Write the failing unit test for the helper**

Create `tests/unit/test_category_map_assembly.py`:

```python
"""Unit tests for _build_hitl_category_map."""

import pytest

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
        # every built-in entry is preserved
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
        # operator pre-declared an override for a tool that is not yet loaded
        category_map = _build_hitl_category_map(
            tool_config=ToolConfig(),
            mcp_tool_names=set(),
            mcp_default=ToolCategory.DANGEROUS,
            mcp_overrides={"future_mcp_tool": ToolCategory.READ_ONLY},
        )
        assert category_map["future_mcp_tool"] == ToolCategory.READ_ONLY

    def test_unknown_builtin_override_key_still_recorded(self):
        # operator can intentionally add an entry for a custom tool they
        # introduced in the same PR; the helper must not silently drop it
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/test_category_map_assembly.py -v
```

Expected: `ImportError: cannot import name '_build_hitl_category_map'`.

- [ ] **Step 3: Add the `_build_hitl_category_map` helper**

At the top of `src/services/agent_service/openai_chat_agent.py` (module level, above the class definition), add:

```python
from src.configs.agent.openai_chat_agent import ToolConfig
from src.models.websocket import ToolCategory
from src.services.agent_service.middleware.hitl_middleware import _DEFAULT_CATEGORIES


def _build_hitl_category_map(
    *,
    tool_config: ToolConfig,
    mcp_tool_names: set[str],
    mcp_default: ToolCategory,
    mcp_overrides: dict[str, ToolCategory],
) -> dict[str, ToolCategory]:
    """Assemble the final tool→category map (see spec §4).

    Order (later wins):
      1. _DEFAULT_CATEGORIES (built-in code catalog)
      2. tool_config.builtin.<group>.hitl_overrides (YAML built-in overrides)
      3. every discovered MCP tool → mcp_default
      4. mcp_overrides (YAML MCP per-tool overrides)
    """
    category_map: dict[str, ToolCategory] = dict(_DEFAULT_CATEGORIES)

    builtin = tool_config.builtin
    for group in (builtin.filesystem, builtin.shell, builtin.web_search):
        category_map.update(group.hitl_overrides)

    for name in mcp_tool_names:
        category_map[name] = mcp_default
    category_map.update(mcp_overrides)

    return category_map
```

- [ ] **Step 4: Validate `tool_config` in `OpenAIChatAgent.__init__` and remove dict alias**

In the same file, update `__init__` (around line 56). Change the signature, add validation, and remove the raw `self.tool_config = tool_config` dict line (there is no more dict form after this task):

```python
    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str | None = None,
        openai_api_base: str | None = None,
        model_name: str | None = None,
        tool_config: ToolConfig | dict | None = None,
        mcp_default_hitl_category: ToolCategory | str = ToolCategory.DANGEROUS,
        mcp_hitl_overrides: dict[str, ToolCategory] | None = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name

        if tool_config is None:
            self._tool_config = ToolConfig()
        elif isinstance(tool_config, dict):
            self._tool_config = ToolConfig.model_validate(tool_config)  # raises on typo
        else:
            self._tool_config = tool_config

        # AgentFactory passes enum values as strings after model_dump() — coerce back
        self._mcp_default_hitl_category = ToolCategory(mcp_default_hitl_category)
        self._mcp_hitl_overrides = {
            k: ToolCategory(v) for k, v in (mcp_hitl_overrides or {}).items()
        }

        self.agent = None
        self._mcp_tools: list = []
        self._personas: dict[str, str] = {}
        super().__init__(**kwargs)
        logger.info(f"Agent initialized: model={self.model_name}")
```

Why the `ToolCategory(...)` coercion: `AgentFactory.get_agent_service` does `OpenAIChatAgentConfig(**kwargs).model_dump()` and then spreads, which serializes enums to their `.value` strings. Re-hydrate them here so downstream code uses real enums.

- [ ] **Step 4b: Update the one remaining dict reader (line 153)**

The existing `initialize_async` reads `(self.tool_config or {}).get("builtin", {})` to configure `ToolGateMiddleware`. Since `self.tool_config` no longer exists, switch to the validated model:

```python
        builtin = self._tool_config.builtin
        tool_gate = ToolGateMiddleware(
            allowed_commands=builtin.shell.allowed_commands or None,
            allowed_dirs=[builtin.filesystem.root_dir] if builtin.filesystem.root_dir else None,
        )
```

This both removes the dict alias and replaces string-key `.get(...)` lookups with typed attribute access. Grep-verify no other readers remain:

```bash
grep -n "self.tool_config" src/services/agent_service/openai_chat_agent.py
```

Expected: no hits.

- [ ] **Step 5: Update `initialize_async` to build and pass `category_map`**

Find the `hitl_gate = HitLMiddleware(mcp_tool_names=mcp_tool_names)` line (around line 164). Replace it with:

```python
        mcp_tool_names = {t.name for t in self._mcp_tools}
        category_map = _build_hitl_category_map(
            tool_config=self._tool_config,
            mcp_tool_names=mcp_tool_names,
            mcp_default=self._mcp_default_hitl_category,
            mcp_overrides=self._mcp_hitl_overrides,
        )
        hitl_gate = HitLMiddleware(category_map=category_map)
        logger.info(
            f"HitL category map assembled: "
            f"{len(category_map)} tools "
            f"({sum(1 for c in category_map.values() if c == ToolCategory.READ_ONLY)} bypass)"
        )
```

- [ ] **Step 6: Verify factory auto-threading — no code change required**

The existing factory already threads every `OpenAIChatAgentConfig` field through. Confirm by reading:

- `src/services/agent_service/agent_factory.py:30` — `return OpenAIChatAgent(**agent_config.model_dump())`
- `src/services/service_manager.py:386-388` — `_inject_extra_config` adds `tool_config` / `mcp_config` to `service_configs` before factory call, and `_initialize_service` at line 129 spreads `llm_config.configs` into `service_configs`.

Because `mcp_default_hitl_category` and `mcp_hitl_overrides` are regular fields on `OpenAIChatAgentConfig` (added in Task 2), they flow:

```
yaml_files/services.yml
  llm_config.configs.mcp_default_hitl_category  ┐
  llm_config.configs.mcp_hitl_overrides         ├─→ service_configs (dict)
  tool_config                                   │     ↓ (factory)
                                                │  OpenAIChatAgentConfig(**kwargs)  ← validates, raises on typo
                                                │     ↓ .model_dump() (serializes enums to .value strings)
                                                └─→ OpenAIChatAgent(**dumped)       ← Step 4 re-hydrates enums
```

Run the verification:

```bash
grep -n "model_dump\|OpenAIChatAgent(" src/services/agent_service/agent_factory.py
grep -n "service_configs\[" src/services/service_manager.py
```

Expected: the two `grep` outputs match the paths above. If the factory ever stops using `**agent_config.model_dump()` (e.g., switches to explicit kwargs), this plan becomes invalid — stop and update the factory first.

**Sample YAML snippet for operators** (document this in the PR description too):

```yaml
llm_config:
  type: "openai_chat_agent"
  configs:
    openai_api_base: "..."
    model_name: "chat_model"
    # NEW in Phase 2 (optional — defaults to dangerous / {})
    mcp_default_hitl_category: dangerous
    mcp_hitl_overrides: {}
```

- [ ] **Step 7: Run unit tests**

```bash
uv run pytest tests/unit/test_category_map_assembly.py tests/unit/test_hitl_middleware.py tests/unit/test_agent_config.py tests/unit/test_hitl_models.py -v
```

Expected: all green.

- [ ] **Step 8: Quick smoke — load the agent config from YAML**

```bash
uv run python -c "
from src.services.agent_service.openai_chat_agent import _build_hitl_category_map
from src.configs.agent.openai_chat_agent import ToolConfig
from src.models.websocket import ToolCategory
m = _build_hitl_category_map(
    tool_config=ToolConfig(),
    mcp_tool_names={'foo'},
    mcp_default=ToolCategory.DANGEROUS,
    mcp_overrides={'foo': ToolCategory.READ_ONLY},
)
assert m['read_file'] == ToolCategory.READ_ONLY
assert m['foo'] == ToolCategory.READ_ONLY
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 9: Commit**

```bash
git add src/services/agent_service/openai_chat_agent.py tests/unit/test_category_map_assembly.py
git commit -m "feat: assemble HitL category_map in OpenAIChatAgent.initialize_async"
```

---

### Task 5: Forward `category` in `_consume_astream()`

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py` (`_consume_astream` only)
- Test: `tests/unit/test_hitl_agent_stream.py`

The stream consumer currently strips the interrupt payload. Add the `category` field with a fail-closed fallback (spec §6).

- [ ] **Step 1: Add/extend the failing test**

Open `tests/unit/test_hitl_agent_stream.py`. Add:

```python
from src.models.websocket import ToolCategory


class TestConsumeAstreamCategory:
    @pytest.mark.asyncio
    async def test_hitl_request_event_includes_category(self):
        # Compose a fake astream iterator that yields an interrupt update
        fake_interrupt = MagicMock()
        fake_interrupt.value = {
            "request_id": "r-1",
            "tool_name": "write_file",
            "tool_args": {"path": "/tmp/x"},
            "category": ToolCategory.STATE_MUTATING.value,
        }

        async def fake_astream():
            yield ("updates", {"__interrupt__": [fake_interrupt]})

        from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

        agent = OpenAIChatAgent(temperature=0.1, top_p=0.9)
        events = [e async for e in agent._consume_astream(fake_astream(), "sess-1")]

        assert events, "no events yielded"
        evt = events[0]
        assert evt["type"] == "hitl_request"
        assert evt["category"] == ToolCategory.STATE_MUTATING.value
        assert evt["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_hitl_request_event_falls_back_to_dangerous(self):
        # older checkpoint / other middleware omits category -> must fail-closed
        fake_interrupt = MagicMock()
        fake_interrupt.value = {
            "request_id": "r-2",
            "tool_name": "legacy_tool",
            "tool_args": {},
        }

        async def fake_astream():
            yield ("updates", {"__interrupt__": [fake_interrupt]})

        from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

        agent = OpenAIChatAgent(temperature=0.1, top_p=0.9)
        events = [e async for e in agent._consume_astream(fake_astream(), "sess-2")]

        assert events[0]["category"] == ToolCategory.DANGEROUS.value
```

Reuse the existing `import pytest`, `from unittest.mock import MagicMock` at the top of the file. If the file does not yet exist, create it with those imports.

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_hitl_agent_stream.py::TestConsumeAstreamCategory -v
```

Expected: `KeyError: 'category'` or the assertion fails — the current code does not forward the field.

- [ ] **Step 3: Update `_consume_astream`**

Find the `__interrupt__` branch in `_consume_astream` (around line 393). Update the yielded dict:

```python
                    if data.get("__interrupt__"):
                        interrupt_value = data["__interrupt__"][0].value
                        yield {
                            "type": "hitl_request",
                            "request_id": interrupt_value["request_id"],
                            "tool_name": interrupt_value["tool_name"],
                            "tool_args": interrupt_value["tool_args"],
                            "session_id": session_id,
                            # fail-closed: handles interrupts from older checkpoints
                            # or any middleware that did not set `category`
                            "category": interrupt_value.get(
                                "category", ToolCategory.DANGEROUS.value
                            ),
                        }
                        return
```

Ensure `ToolCategory` is imported at the top of the file (the Task 4 edit may already have it — if not, add `from src.models.websocket import ToolCategory`).

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_hitl_agent_stream.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/services/agent_service/openai_chat_agent.py tests/unit/test_hitl_agent_stream.py
git commit -m "feat: forward HitL category in hitl_request stream event"
```

---

### Task 6: Add structural coverage test for `_DEFAULT_CATEGORIES`

**Files:**
- Create: `tests/structural/test_default_categories_coverage.py`

Locks the invariant: every tool the agent can actually load is present in `_DEFAULT_CATEGORIES`. Prevents LangChain version drift and forgotten registrations (spec Test Strategy).

- [ ] **Step 1: Enumerate every built-in tool source**

```bash
grep -rn "name: str = " src/services/agent_service/tools/ | head
grep -rn "from langchain_community.tools" src/services/agent_service/tools/ | head
```

Note each source — `ToolRegistry.get_enabled_tools()` covers the YAML-gated ones (filesystem, shell, web_search); `DelegateTaskTool`, `UpdateUserProfileTool`, memory tools (`add_memory`, `update_memory`, `delete_memory`, `search_memory`), knowledge tools (`search_knowledge`, `read_note`) are registered elsewhere.

- [ ] **Step 2: Write the structural test**

Create `tests/structural/test_default_categories_coverage.py`:

```python
"""Structural test: _DEFAULT_CATEGORIES must cover every built-in tool the agent loads."""

import pytest

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
    ).model_dump()
    for tool in ToolRegistry(fully_enabled).get_enabled_tools():
        names.add(tool.name)

    # 2. Tools registered outside the registry (enumerate explicitly — if new
    # ones are added, extend this list AND _DEFAULT_CATEGORIES).
    from src.services.agent_service.tools.delegate import DelegateTaskTool

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
```

If a tool class above does not actually exist in the codebase yet (e.g., knowledge tools), remove that line from the fixed list. The test's job is coverage, not aspiration — it must reflect reality.

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/structural/test_default_categories_coverage.py -v
```

Expected: green. If it fails, either (a) a tool name is missing from `_DEFAULT_CATEGORIES` (add it) or (b) the enumeration picks up a tool that does not exist as a registered tool (remove it from the fixed list).

- [ ] **Step 4: Commit**

```bash
git add tests/structural/test_default_categories_coverage.py
git commit -m "test: structural coverage for _DEFAULT_CATEGORIES"
```

---

### Task 7: Update E2E tests

**Files:**
- Modify: `tests/e2e/test_hitl_e2e.py`

Ensure live-flow `hitl_request` events include `category` and a `read_only` tool executes without prompting (spec Test Strategy).

- [ ] **Step 1: Inspect existing E2E cases**

```bash
grep -n "hitl_request\|approved" tests/e2e/test_hitl_e2e.py | head -30
```

Find the section that awaits a `hitl_request` frame. Add a `category` assertion next to the existing `tool_name` / `request_id` checks.

- [ ] **Step 2: Add the category assertion in every existing `hitl_request` receive path**

For every block that looks like `assert msg["type"] == "hitl_request"`, add:

```python
assert msg["type"] == "hitl_request"
assert msg["category"] in {"state_mutating", "external", "dangerous"}
```

(Since we expect approval-requiring tools in the existing flows, `read_only` should not appear here.)

- [ ] **Step 3: Add a `read_only` bypass test — deterministic, not LLM-choice dependent**

Skip the LLM-selection problem entirely by calling the middleware directly with a mocked interrupt. This verifies the contract ("read_only → no interrupt, handler runs") end-to-end through the real middleware instance, without needing the agent to choose a specific tool at runtime:

```python
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_read_only_tool_bypasses_hitl_via_middleware():
    """read_only category must not trigger interrupt() at the middleware layer."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.models.websocket import ToolCategory
    from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware

    mw = HitLMiddleware(category_map={"search_memory": ToolCategory.READ_ONLY})
    request = MagicMock()
    request.tool_call = {"name": "search_memory", "args": {"query": "cat"}}
    handler = AsyncMock(return_value="memory hit")

    with patch(
        "src.services.agent_service.middleware.hitl_middleware.interrupt"
    ) as mock_interrupt:
        result = await mw.awrap_tool_call(request, handler)

    mock_interrupt.assert_not_called()
    handler.assert_awaited_once_with(request)
    assert result == "memory hit"
```

Note: this sits in `tests/e2e/test_hitl_e2e.py` because it's part of the HitL flow contract documentation, but it does not require live services. Keep the full-stack WebSocket E2E tests in the same file focused on the non-bypass path (which is already flow-driven and works reliably because the LLM is forced to call dangerous tools in those scenarios). Do not add a flaky LLM-driven bypass test — if category routing breaks inside middleware, the middleware-level assertion catches it, and the existing `test_hitl_middleware.py` unit test already covers this in isolation.

- [ ] **Step 4: Run E2E suite**

```bash
bash scripts/e2e.sh
```

Expected: green. If environment services (MongoDB, vLLM, IrodoriTTS) aren't running locally, spin them up per the README before running.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_hitl_e2e.py
git commit -m "test: assert category field in hitl_request E2E + read_only bypass"
```

---

### Task 8: Update data flow documentation

**Files:**
- Modify: `docs/data_flow/agent/HITL_GATE_FLOW.md`
- Modify: `docs/data_flow/chat/ADD_CHAT_MESSAGE.md`
- Modify: `docs/data_flow/chat/CONTEXT_INJECTION_FLOW.md`

The existing diagrams describe the Phase 1 binary classifier (`is_dangerous`, "MCP 도구 + delegate_task"). Phase 2 changes the shape of the flow — category-based routing, category in the interrupt payload, code-authoritative catalog, YAML overrides. Operators and reviewers read these flow docs before touching the middleware, so they must match shipped behavior.

Respect `docs/CLAUDE.md` 200-line rule — the happy path stays in the main body; edge cases (Phase 1 fallback semantics, MCP enumeration failure) go into the Appendix.

- [ ] **Step 1: Rewrite `docs/data_flow/agent/HITL_GATE_FLOW.md`**

Make these concrete edits (do **not** rewrite the whole file — diff-style changes only):

1. Bump `Updated:` to today's date.
2. Replace the §2-1 "도구 분류" table with the 4-tier category table — copy from spec `## Tool Categories`. Add a one-line pointer: "카테고리 정의는 `_DEFAULT_CATEGORIES` (`hitl_middleware.py`)가 단일 진실 소스. YAML `hitl_overrides`로 per-tool override."
3. Update §2-1's final sentence: `분류 로직: HitLMiddleware.is_dangerous(tool_name)` → `분류 로직: HitLMiddleware.get_category(tool_name) — _DEFAULT_CATEGORIES + YAML overrides + MCP default/overrides가 startup에 병합된 category_map을 사용. 미등록 툴은 fail-closed로 dangerous.`
4. Update §2-2 interrupt payload line: `interrupt({tool_name, tool_args, request_id})` → `interrupt({tool_name, tool_args, request_id, category})`.
5. Update §4 `hitl_request` 메시지 형식 JSON example to include `"category": "state_mutating"` as an example value; also correct `turn_id` → `session_id` if it is wrong there (verify against `HitLRequestMessage` in `src/models/websocket.py`).
6. Add a new §2-5 subsection titled "바이패스 동작":

   > `read_only` 카테고리는 middleware가 `interrupt()`를 호출하지 않고 `handler(request)`를 직접 await. 프론트 `hitl_request` 이벤트가 발생하지 않음. 로그: `HitL gate: '{tool}' bypass (category=read_only)`.

7. Appendix §A 구현 파일 표 업데이트: middleware entry의 `is_dangerous` 문구 제거, 새 entry 추가:
   - `src/services/agent_service/openai_chat_agent.py::_build_hitl_category_map` — category_map 조립 (spec §4)
   - `src/configs/agent/openai_chat_agent.py::FilesystemToolConfig/ShellToolConfig/WebSearchToolConfig::hitl_overrides` — per-tool YAML override
8. Appendix §D PatchNote에 줄 추가:

   > `YYYY-MM-DD`: Phase 2 — 4-tier category 시스템 도입. `is_dangerous` → `get_category`, interrupt payload에 `category` 추가, `_DEFAULT_CATEGORIES` 단일 소스 + YAML `hitl_overrides`/`mcp_hitl_overrides`. Issue #42 / PR #(TBD).

9. Verify the file is still under the 200-line main body (appendix can overflow) via `awk 'NR<=200' docs/data_flow/agent/HITL_GATE_FLOW.md | wc -l` — if the main body grows past 200, move older Phase 1 troubleshooting notes into Appendix.

- [ ] **Step 2: Update `docs/data_flow/chat/ADD_CHAT_MESSAGE.md`**

1. Line ~60 mermaid note: `MCP 도구 또는 delegate_task 호출 시<br/>HitLMiddleware가 interrupt() 발생` → `비-read_only 카테고리 툴 호출 시<br/>HitLMiddleware가 interrupt(category 포함) 발생`.
2. Line ~61 mermaid frame: `BE-->>FE: hitl_request (tool_name, tool_args, request_id)` → `BE-->>FE: hitl_request (tool_name, tool_args, request_id, category)`.
3. Line ~129-134 §HitL Gate section:
   - **Trigger** 문구: "MCP 도구 또는 `delegate_task` 호출 시" → "non-`read_only` 카테고리 툴 호출 시"
   - **Safe tools** 표현을 **Bypass tools (`read_only`)**로 교체, 예시를 실제 `_DEFAULT_CATEGORIES`의 read_only 엔트리(`read_file`, `list_directory`, `search_memory`, `search_knowledge`, `read_note`, `duckduckgo_search`)로 나열
   - **Resume** 문구는 변경 없음
4. 관련 문서 링크 목록(line ~141)에 spec 링크 추가:

   > - [HitL Phase 2 Spec](../../superpowers/specs/2026-04-17-hitl-phase2-category-approval-design.md)

- [ ] **Step 3: Update `docs/data_flow/chat/CONTEXT_INJECTION_FLOW.md`**

1. Line ~70 HitLMiddleware 설명:

   기존:
   > **HitLMiddleware** (PR #36): ToolGate 다음 2번째 위치. MCP 도구 + `delegate_task` 호출 시 `interrupt()`로 FE 승인 게이트. Safe 도구(`search_memory`, `update_user_profile`)는 통과.

   변경:
   > **HitLMiddleware** (PR #36 → Phase 2 #42): ToolGate 다음 2번째 위치. `_DEFAULT_CATEGORIES` + YAML override로 빌드된 category_map 기준으로 `read_only` 바이패스, 그 외(`state_mutating`/`external`/`dangerous`)는 `interrupt()`로 FE 승인 게이트. Interrupt payload에 `category` 포함.

- [ ] **Step 4: Run dead-link / markdown check**

```bash
bash scripts/check_docs.sh 2>&1 | tail -20
```

Expected: no new errors. If pre-existing warnings exist, ignore those that are not in the three files just edited.

- [ ] **Step 5: Commit**

```bash
git add docs/data_flow/agent/HITL_GATE_FLOW.md \
        docs/data_flow/chat/ADD_CHAT_MESSAGE.md \
        docs/data_flow/chat/CONTEXT_INJECTION_FLOW.md
git commit -m "docs: update HitL data flow for Phase 2 category system"
```

---

### Task 9: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full unit test suite**

```bash
uv run pytest -m "not slow and not e2e" -q
```

Expected: all green. Fix any remaining test that referenced the old `is_dangerous` API or constructed `HitLRequestMessage` without `category`.

- [ ] **Step 2: Run lint and structural tests**

```bash
bash scripts/lint.sh
```

Expected: clean (ruff + black + structural).

- [ ] **Step 3: Run the full E2E suite**

```bash
bash scripts/e2e.sh
```

Expected: green. Per `CLAUDE.md` this gate is required before the PR can be opened.

- [ ] **Step 4: YAML sweep (final)**

```bash
grep -rn "default_hitl_category:" yaml_files/ ; \
grep -rn "builtin_tools:" yaml_files/
```

Expected: no hits (pre-flight should have caught them).

- [ ] **Step 5: Manual smoke — start the dev server**

```bash
uv run uvicorn "src.main:get_app" --factory --port 5500
```

Look for the new log line on startup:

```
INFO  | HitL category map assembled: N tools (K bypass)
```

In a second shell, drive the WebSocket client example:

```bash
uv run python examples/ws_chat_client.py --prompt "/tmp/hitl-phase2에 test.txt 파일을 만들어줘" --session-id phase2-smoke
```

Expected console output from the client: a `hitl_request` frame with `"category": "state_mutating"` (because `write_file` is state-mutating). Approve it in the client UI or send `{"type":"hitl_response","request_id":"<from-prev-frame>","approved":true}` manually, and the flow continues. Stop the server with Ctrl-C once you have seen the category field. If `examples/ws_chat_client.py` does not exist, use `examples/websocket_stream_demo.py` or whatever the current example client is — `ls examples/` to confirm the filename.

- [ ] **Step 6: Commit any doc updates if log output diverged from spec**

```bash
git status
# only commit if there are deliberate changes; skip otherwise
```

- [ ] **Step 7: Open the PR**

```bash
git push -u origin feat/hitl-phase2-category-approval
gh pr create --title "feat: HitL Phase 2 — category-based selective approval (#42)" \
  --body "$(cat <<'EOF'
## Summary
- Replace `HitLMiddleware`'s binary classifier with a 4-tier category system (`read_only` / `state_mutating` / `external` / `dangerous`).
- Code-authoritative built-in catalog (`_DEFAULT_CATEGORIES`); YAML exposes only `hitl_overrides`. MCP tools default to `mcp_default_hitl_category` (fail-closed) with opt-in `mcp_hitl_overrides`.
- Interrupt payload now carries `category`; forwarded through `_consume_astream` with a fail-closed default for legacy checkpoints.

## Test plan
- [ ] `uv run pytest -m "not slow and not e2e"` — all green
- [ ] `bash scripts/lint.sh` — clean
- [ ] `bash scripts/e2e.sh` — all green, including new `read_only` bypass case
- [ ] Manual: start dev server, verify startup log `HitL category map assembled: ...` and `hitl_request` frames include `category`

Closes #42.
EOF
)"
```

---

## Rollback Plan

If any task fails irrecoverably:

1. `git log --oneline feat/hitl-phase2-category-approval` — identify the last green commit.
2. `git reset --hard <sha>` to drop the bad commits locally.
3. Never `git push --force` without confirming with the user first.

Because each task commits independently, rollbacks shrink to "drop last N commits" — never a bulk revert.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-hitl-phase2-category-approval.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
