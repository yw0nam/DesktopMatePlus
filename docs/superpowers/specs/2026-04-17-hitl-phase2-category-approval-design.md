# HitL Phase 2: Category-Based Selective Approval

**Date:** 2026-04-17
**Issue:** #42
**Component:** agent service (`src/services/agent_service/`)

## Summary

Replace the binary dangerous/safe classification in `HitLMiddleware` with a 4-tier tool category system. Built-in tool categories are defined authoritatively in code (`_DEFAULT_CATEGORIES`); YAML only exposes per-tool overrides. MCP tools default to `mcp_default_hitl_category` (fail-closed: `dangerous`) with optional per-tool overrides. Unregistered tools default to `dangerous`.

## Design Decisions

- **Code-authoritative built-in catalog.** `_DEFAULT_CATEGORIES` is the single source of truth for built-in tool names and their categories. YAML does not expose a group-level `default_hitl_category` for built-ins, because it would duplicate the code-level catalog and introduce a second source of truth that can drift. YAML retains only per-tool `hitl_overrides` for operational tuning.
- **MCP is YAML-driven.** MCP tool names are discovered at runtime, so their default lives in YAML (`mcp_default_hitl_category`) rather than code, with `mcp_hitl_overrides` for verified-safe tools.
- **Fail-closed.** Any tool not present in the final merged `category_map` is treated as `dangerous` by `HitLMiddleware.get_category()`.

## Tool Categories

| Category | Approval | Examples |
|----------|----------|----------|
| `read_only` | Bypass (auto-execute) | `read_file`, `list_directory`, `search_knowledge`, `read_note`, `search_memory`, `duckduckgo_search` |
| `state_mutating` | Required | `write_file`, `add_memory`, `update_memory`, `delete_memory`, `update_user_profile` |
| `external` | Required | `delegate_task` |
| `dangerous` | Required | `terminal`, MCP tools (default) |

All three non-bypass categories currently behave identically (interrupt and request approval). Separating them now enables future policy extensions (e.g., session-level batch approval for `state_mutating`).

## YAML Configuration

The existing YAML layout (`yaml_files/services.yml` and siblings) places agent settings under `llm_config:` (loaded as `OpenAIChatAgentConfig`) and tool settings under `tool_config:` (loaded as `ToolConfig`). Phase 2 adds fields in both places; no new top-level keys are introduced.

Built-in tool categories are defined authoritatively in code (`_DEFAULT_CATEGORIES`, see section 4). YAML exposes per-tool `hitl_overrides` for operational tuning only. MCP tools, whose names are discovered at runtime, are governed by `mcp_default_hitl_category` with an optional `mcp_hitl_overrides` map.

```yaml
# -- HitL (Human-in-the-Loop) tool approval policy --
# Category behavior:
#   read_only       -> auto-execute without approval
#   state_mutating  -> requires user approval (file writes, memory changes, etc.)
#   external        -> requires user approval (external system calls)
#   dangerous       -> requires user approval (shell execution, unclassified tools)
#
# Built-in tool defaults live in code (_DEFAULT_CATEGORIES). YAML only overrides.
# MCP tools default to mcp_default_hitl_category (fail-closed: dangerous).
# Any tool not in the final merged map is treated as dangerous.

llm_config:
  # ... existing fields (openai_api_key, openai_api_base, model_name, ...) ...

  # MCP tools are dynamically loaded from external servers.
  # Default to dangerous since their behavior is unknown at config time.
  # Only override tools that have been verified as safe.
  mcp_default_hitl_category: dangerous
  mcp_hitl_overrides: {}

tool_config:
  builtin:
    filesystem:
      enabled: true
      # Optional per-tool override. Empty/omitted means "use _DEFAULT_CATEGORIES".
      hitl_overrides: {}
    shell:
      enabled: true
      hitl_overrides: {}
    web_search:
      enabled: true
      hitl_overrides: {}
```

## Code Changes

### 1. ToolCategory Enum

Add the enum to `src/models/websocket.py` (same module as `HitLRequestMessage` — keeps the interrupt-payload contract and its schema co-located). Config models (`src/configs/agent/openai_chat_agent.py`) and middleware (`src/services/agent_service/middleware/hitl_middleware.py`, which hosts `_DEFAULT_CATEGORIES`) import from here.

**Import direction (do not invert):** `hitl_middleware` → `src/models/websocket` (one way). `src/models/websocket.py` must remain a leaf schema module with no imports from `services/` or `configs/` — keeping it import-free prevents cycles as the catalog grows.

```python
class ToolCategory(str, Enum):
    READ_ONLY = "read_only"
    STATE_MUTATING = "state_mutating"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"
```

### 2. Config Model Changes (`src/configs/agent/openai_chat_agent.py`)

Actual class names in the current codebase (verify before editing): `FilesystemToolConfig` (lowercase `s`), `ShellToolConfig`, `WebSearchToolConfig`, `BuiltinToolConfig`, `ToolConfig`, `OpenAIChatAgentConfig`. Add `hitl_overrides` to each built-in tool config, and `mcp_default_hitl_category` / `mcp_hitl_overrides` to `OpenAIChatAgentConfig`. No group-level `default_hitl_category` — built-in defaults live in `_DEFAULT_CATEGORIES` (section 4).

Also add `model_config = ConfigDict(extra="forbid")` to the three tool config classes **and** `OpenAIChatAgentConfig`. The current codebase uses Pydantic's default `extra="ignore"`, which silently drops unknown keys — including stale `default_hitl_category` entries in old YAML. `extra="forbid"` forces startup failure on drift. Before enabling `extra="forbid"` globally, verify no existing YAML carries unrelated extra keys: `grep -rn "^\s*[a-zA-Z_]\+:" yaml_files/services*.yml` against current model fields (or run the migration once in CI with `extra="forbid"` to surface stragglers). If alien keys exist, scope the change narrowly to the new HitL fields via a validator instead of a global flag.

```python
from pydantic import BaseModel, ConfigDict, Field

class FilesystemToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)

class ShellToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)

class WebSearchToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)

class OpenAIChatAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # ... existing fields ...
    mcp_default_hitl_category: ToolCategory = ToolCategory.DANGEROUS
    mcp_hitl_overrides: dict[str, ToolCategory] = Field(default_factory=dict)
```

**Validation note (important).** The two YAML sections take different current paths:

- `llm_config:` → already validated. `service_manager.initialize_agent_service()` loads it with `config_key="llm_config"` and the `_initialize_service` helper constructs `OpenAIChatAgentConfig` via Pydantic. The new `mcp_default_hitl_category` / `mcp_hitl_overrides` fields therefore get validated at startup **without new plumbing**.
- `tool_config:` → **currently NOT validated at startup**. `service_manager._inject_extra_config` passes it to `OpenAIChatAgent.__init__` as a raw `dict | None` (`src/services/agent_service/openai_chat_agent.py:63,71`); only `ToolRegistry.__init__` later calls `ToolConfig.model_validate(...)` on the `builtin` sub-tree. For `hitl_overrides` typos to fail fast, Phase 2 **must** tighten this path.

**Decision: validate `tool_config` in `OpenAIChatAgent.__init__`** (smallest blast radius; keeps `service_manager` untouched). Change the signature from `tool_config: dict | None = None` to accept either a dict or a `ToolConfig`, and at the top of `__init__` do:

```python
if tool_config is None:
    self._tool_config = ToolConfig()
elif isinstance(tool_config, dict):
    self._tool_config = ToolConfig.model_validate(tool_config)  # raises on typo
else:
    self._tool_config = tool_config
```

Then reuse `self._tool_config` in both `ToolRegistry(self._tool_config)` and the category-map builder (section 4), avoiding double validation. `Field(default_factory=dict)` ensures each instance gets its own mutable dict.

### 3. HitLMiddleware Refactor

Replace `is_dangerous()` with `get_category()` and `requires_approval()`.

**Constructor:** Accepts `category_map: dict[str, ToolCategory]` (fully resolved mapping built externally).

```python
class HitLMiddleware(AgentMiddleware):
    _BYPASS_CATEGORIES: frozenset[ToolCategory] = frozenset({ToolCategory.READ_ONLY})

    def __init__(self, category_map: dict[str, ToolCategory]) -> None:
        self._category_map = category_map

    def get_category(self, tool_name: str) -> ToolCategory:
        return self._category_map.get(tool_name, ToolCategory.DANGEROUS)

    def requires_approval(self, tool_name: str) -> bool:
        return self.get_category(tool_name) not in self._BYPASS_CATEGORIES
```

**`awrap_tool_call()`:** Include `category` in the interrupt payload.

```python
interrupt({
    "tool_name": tool_name,
    "tool_args": tool_args,
    "request_id": str(uuid4()),
    "category": self.get_category(tool_name).value,
})
```

Resume path unchanged: check `approved` boolean, execute or deny.

**Middleware ordering.** `ToolGateMiddleware` (static whitelist / metacharacter rejection, fail-closed) must run **before** `HitLMiddleware` in the middleware list. ToolGate rejects disallowed invocations synchronously without user interaction; HitL only gates calls that already passed ToolGate. This mirrors the current Phase 1 order — do not change it.

**Observability.** Log each categorization and approval decision at INFO level with `request_id`, `tool_name`, and `category` (follow the existing logging pattern in `hitl_middleware.py`). This gives ops a category-distribution signal without adding new metrics infrastructure.

### 4. Category Map Assembly (`openai_chat_agent.initialize_async()`)

Build the complete `category_map` by merging layers. The first step explicitly validates the YAML via Pydantic so that `ToolCategory` typos in `hitl_overrides` / `mcp_*` fields are caught at startup:

```
YAML loading (service_manager)
  llm_config:  → OpenAIChatAgentConfig.model_validate(...)    [already happens]
  tool_config: → passed as raw dict to OpenAIChatAgent.__init__
                 ↓
                 OpenAIChatAgent.__init__ validates dict → ToolConfig   [NEW, §2]
                 ↓
                 stored as self._tool_config : ToolConfig
  ────────────────────────────────────────────────────────────────────
  Now all HitL-relevant config is strongly typed. Build category_map:

  _DEFAULT_CATEGORIES (ALL builtin tools — explicit name-to-category mapping)
    ↓ merge (YAML overrides win over defaults)
  self._tool_config.builtin.<group>.hitl_overrides (per-tool exceptions)
    ↓ merge (MCP tool names discovered at runtime via mcp_client.get_tools())
  MCP tools → self._agent_config.mcp_default_hitl_category applied to every discovered name
    ↓ merge (YAML overrides win over MCP default)
  self._agent_config.mcp_hitl_overrides (per-MCP-tool exceptions)
    = final category_map: dict[str, ToolCategory]
```

`_DEFAULT_CATEGORIES` is a module-level constant that explicitly maps **every** built-in tool name to its category. This avoids the need to discover built-in tool names at runtime — the mapping is authoritative and complete. When adding a new built-in tool, add its entry here; if omitted, the fail-closed default (`DANGEROUS`) applies at lookup time via `HitLMiddleware.get_category()`.

**MCP enumeration (runtime):** `initialize_async()` already calls `await mcp_client.get_tools()` to load MCP tools. The returned tool names are used to seed `category_map` entries with `mcp_default_hitl_category`; `mcp_hitl_overrides` is then layered on top. If MCP loading fails (see "Stateless MCP Client" pattern in `backend/CLAUDE.md`), no MCP entries are added — the final `category_map` simply contains built-ins only.

**Checkpoint-resume interaction (intentional fail-closed).** If the agent resumes from a checkpoint and MCP loading has just failed, a tool name previously approved by the user may now be absent from `category_map`. `get_category()` will return `DANGEROUS` via the default branch, re-prompting the user. This matches Phase 1 behavior (MCP ≡ dangerous) and is the intended fail-closed path — the spec accepts the one-extra-prompt UX cost as the price of safety. Do not cache prior approvals across MCP outages.

```python
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
```

YAML `hitl_overrides` can still override any entry above (e.g., promote `duckduckgo_search` to `state_mutating` if a custom search tool with side effects is swapped in).

### 5. HitLRequestMessage Model Change

Add `category` field:

```python
# NOTE: The runtime WebSocket pipeline yields a raw dict from _consume_astream
# (see section 6) — this Pydantic model is not instantiated today. It exists as
# schema documentation and will become live if/when the pipeline switches to
# Pydantic serialization. Keeping the model in sync with the dict contract
# prevents the schema from drifting silently.
class HitLRequestMessage(BaseMessage):
    type: MessageType = MessageType.HITL_REQUEST
    request_id: str
    tool_name: str
    tool_args: dict
    session_id: str
    category: ToolCategory
```

### 6. `_consume_astream()` Change (REQUIRED)

The current `_consume_astream()` manually constructs the `hitl_request` dict by explicitly extracting fields from the interrupt value. **`category` must be added here** — it is NOT forwarded automatically.

Current code:
```python
yield {
    "type": "hitl_request",
    "request_id": interrupt_value["request_id"],
    "tool_name": interrupt_value["tool_name"],
    "tool_args": interrupt_value["tool_args"],
    "session_id": session_id,
}
```

Updated code:
```python
yield {
    "type": "hitl_request",
    "request_id": interrupt_value["request_id"],
    "tool_name": interrupt_value["tool_name"],
    "tool_args": interrupt_value["tool_args"],
    "session_id": session_id,
    # fail-closed default handles interrupts from older checkpoints or
    # any other middleware that did not set `category`
    "category": interrupt_value.get("category", ToolCategory.DANGEROUS.value),
}
```

**Wire format is string, not enum.** `HitLMiddleware.awrap_tool_call()` sends `self.get_category(tool_name).value` (a `str`) into the interrupt payload, so `interrupt_value["category"]` is always a string here. The `HitLRequestMessage` Pydantic model in section 5 types it as `ToolCategory`, which Pydantic V2 coerces from the string on validation — future pipeline changes that start actually instantiating the model should use `model_dump(mode="json")` (or `ConfigDict(use_enum_values=True)`) to keep the wire format a string end-to-end.

### 7. No Changes Required

- `HitLResponseMessage` — unchanged (`approved: bool` only)
- WebSocket routing — unchanged
- `handle_hitl_response()` — unchanged
- `resume_after_approval()` — unchanged

**Out of scope (tracked separately):** Frontend usage of the new `category` field — e.g., differentiating warning colors/copy for `state_mutating` vs `external` vs `dangerous`, or batch-approval UI for a future session policy — is intentionally deferred. Backend emits `category`; UI consumption belongs to a follow-up issue.

## Test Strategy

### Unit Tests (modify existing + add new)

**`test_hitl_middleware.py`:**
- Refactor existing `is_dangerous()` tests → `get_category()` / `requires_approval()`
- `read_only` tool → bypass (no interrupt)
- **Per-category behavior divergence (one test per category):**
  - `state_mutating` tool → interrupt fires AND `interrupt_value["category"] == "state_mutating"`
  - `external` tool → interrupt fires AND `interrupt_value["category"] == "external"`
  - `dangerous` tool → interrupt fires AND `interrupt_value["category"] == "dangerous"`
  - Rationale: separating categories is only meaningful if each preserves its label end-to-end. These tests lock the contract that future policy extensions (e.g., per-category batch approval) will depend on.
- Unregistered tool → `dangerous` default (fail-closed)
- `category_map` construction: `_DEFAULT_CATEGORIES` + YAML overrides + MCP defaults + MCP overrides merge correctly

**`test_hitl_models.py`:**
- `HitLRequestMessage` serialization includes `category` field with `ToolCategory` enum value

**`test_hitl_agent_stream.py`:**
- Interrupt payload contains `category` field
- `_consume_astream` yields `category` in `hitl_request` event

**`test_category_map_assembly.py` (new):**
- `_DEFAULT_CATEGORIES` + YAML overrides merge: override wins
- MCP tool not in overrides → defaults to `dangerous`
- MCP tool in overrides → uses override value
- Complete assembly produces expected final map

**`test_default_categories_coverage.py` (new, structural):**
- Instantiate every built-in tool source: `ToolRegistry(<minimal-enabled-config>).get_enabled_tools()` plus any tools registered outside the registry (`DelegateTaskTool`, memory/knowledge/profile tools, etc. — enumerate them explicitly in the test).
- Assert `{t.name for t in all_builtin_tools} ⊆ _DEFAULT_CATEGORIES.keys()`.
- Rationale: LangChain community tools (`ReadFileTool`, `WriteFileTool`, `ListDirectoryTool`, `DuckDuckGoSearchRun`, …) derive `.name` from their class and that name can shift between LangChain versions. A code-level constant keyed by string can silently drift from the real `.name`; this test catches version bumps as well as newly added tools. Without it, a drifted name would silently fall through to the `DANGEROUS` default — safe, but surprising and a subtle UX regression.

### E2E Tests

- Existing approve/deny flows: verify `hitl_request` includes `category` field and value is valid `ToolCategory`
- Safe tool (e.g., `read_file`): no `hitl_request` emitted, executes directly

## Adding New Tools (Operator Guide)

This section is the contract for **anyone adding a tool to the agent**. Follow the matching path.

### Path A — New built-in tool

1. Implement the tool class under `backend/src/services/agent_service/tools/` and register it (via `ToolRegistry` or the relevant factory).
2. Open `hitl_middleware.py` (or wherever `_DEFAULT_CATEGORIES` lives) and add an entry:
   ```python
   _DEFAULT_CATEGORIES: dict[str, ToolCategory] = {
       ...
       "my_new_tool": ToolCategory.STATE_MUTATING,  # pick one
   }
   ```
3. Choose the category by asking **"what does this tool do to the world?"**
   - Pure reads (file, search, memory lookup) → `READ_ONLY` — auto-executes, no prompt.
   - Writes file / memory / DB / user profile → `STATE_MUTATING`.
   - Delegates to another agent / sandbox / external runner → `EXTERNAL`.
   - Shell / arbitrary code / unknown effects → `DANGEROUS`.
   - When in doubt, pick the more restrictive one. Downgrading later is one-line; upgrading after an incident is a PR + changelog.
4. The structural test `test_default_categories_coverage.py` will fail the build if you forget step 2. Even if it slipped through, `get_category()` returns `DANGEROUS` by default — the worst case is a surprising approval prompt, not silent unsafe execution.
5. If an individual deployment needs a different category from the code default (rare), set it per-environment without editing code:
   ```yaml
   tool_config:
     builtin:
       filesystem:
         hitl_overrides:
           my_new_tool: read_only   # only in this YAML
   ```

### Path B — New MCP server / MCP tools

No code change needed. MCP tools are discovered at runtime via `await mcp_client.get_tools()`.

1. Register the MCP server in the usual way (existing workflow, unchanged).
2. On first startup, every tool the server exposes is classified as `mcp_default_hitl_category` — which is `dangerous` by default. Expect an approval prompt for every call.
3. For tools you have **verified as safe** (source-read, opinion-free queries, etc.), opt them in explicitly via YAML:
   ```yaml
   llm_config:
     mcp_default_hitl_category: dangerous     # keep the default strict
     mcp_hitl_overrides:
       github_search_issues: read_only        # bypass approval
       notion_search: read_only
       github_create_issue: state_mutating    # downgrade dangerous → state_mutating
   ```
4. Use the exact tool `.name` the MCP server reports. Typos are rejected at startup because `ToolCategory` is a validated enum — but a stale name (e.g., after the server renames a tool) will silently fall back to `dangerous`. Re-verify MCP overrides whenever an MCP server is upgraded.

### Path C — Changing the category of an existing tool

Decide scope first:

| Change should apply to... | Edit this |
|---------------------------|-----------|
| Every deployment, always | `_DEFAULT_CATEGORIES` (built-in) or the tool's existing classification — update the constant + test fixture in the same PR. |
| One environment (e.g., e2e, staging, docker) | `hitl_overrides` in that environment's YAML file (`services.e2e.yml`, etc.). Leave the code default alone. |

The code-level constant is the source of truth for what the tool **is**. YAML overrides express **how this deployment wants to run it**. Keep them in that order — do not rely on YAML to document the tool's true nature.

## Migration

No data migration needed. The change is purely in middleware logic and config schema.

**YAML schema change (requires explicit cleanup).** Early Phase 2 drafts proposed a per-group `default_hitl_category` field on `FilesystemToolConfig` / `ShellToolConfig` / `WebSearchToolConfig`. That field is **not** part of the final design — built-in defaults are code-owned via `_DEFAULT_CATEGORIES`. The current config models rely on Pydantic V2's default `extra="ignore"`, which means **a stale `default_hitl_category:` key in YAML is silently dropped today — operators get no warning that their intent is being ignored.** This PR tightens the config by adding `model_config = ConfigDict(extra="forbid")` (see section 2), so stale keys will raise `ValidationError` on startup after the upgrade. Before deploying, run both: `grep -rn "default_hitl_category:" yaml_files/` (remove every match) **and** `grep -rn "builtin_tools:" yaml_files/` (rename to `tool_config.builtin` — early drafts used `agent.builtin_tools` which was never the real schema). Only `hitl_overrides` (per-tool) remains for built-ins.

Existing YAML configs without any of the new fields (`hitl_overrides`, `mcp_default_hitl_category`, `mcp_hitl_overrides`) will use Pydantic defaults (`{}`, `DANGEROUS`, `{}` respectively) — no action needed.

**Behavioral change from Phase 1:** In Phase 1, all non-MCP/non-delegate built-in tools auto-execute without approval. In Phase 2, `_DEFAULT_CATEGORIES` explicitly classifies every built-in tool. If a new tool is added but not registered in `_DEFAULT_CATEGORIES`, it will default to `dangerous` and require approval — this is intentional (fail-closed). The `test_default_categories_coverage.py` structural test (see Test Strategy) enforces this invariant at build time.

**`delegate_task` categorization rationale.** Phase 1 treats `delegate_task` as a dangerous-equivalent (always requires approval). Phase 2 retains that approval requirement but labels it `EXTERNAL` to carry intent forward: delegation hits another agent / sandbox, so a future policy (e.g., per-target auto-approve for trusted sandboxes, or session-level batch approval) will key off this category. No behavioral change today. Track the follow-up under issue #42's roadmap.
