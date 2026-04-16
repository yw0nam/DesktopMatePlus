# HitL Phase 2: Category-Based Selective Approval

**Date:** 2026-04-17
**Issue:** #42
**Component:** agent service (`src/services/agent_service/`)

## Summary

Replace the binary dangerous/safe classification in `HitLMiddleware` with a 4-tier tool category system. Categories are configured per tool-group in YAML with group-level defaults and per-tool overrides. Unregistered tools default to `dangerous` (fail-closed).

## Tool Categories

| Category | Approval | Examples |
|----------|----------|----------|
| `read_only` | Bypass (auto-execute) | `read_file`, `list_directory`, `search_knowledge`, `read_note`, `search_memory`, `duckduckgo_search` |
| `state_mutating` | Required | `write_file`, `add_memory`, `update_memory`, `delete_memory`, `update_user_profile` |
| `external` | Required | `delegate_task` |
| `dangerous` | Required | `terminal`, MCP tools (default) |

All three non-bypass categories currently behave identically (interrupt and request approval). Separating them now enables future policy extensions (e.g., session-level batch approval for `state_mutating`).

## YAML Configuration

Categories are defined at the tool-group level with `default_hitl_category` and optional `hitl_overrides` for individual tools within that group.

```yaml
agent:
  # -- HitL (Human-in-the-Loop) tool approval policy --
  # Category behavior:
  #   read_only       -> auto-execute without approval
  #   state_mutating  -> requires user approval (file writes, memory changes, etc.)
  #   external        -> requires user approval (external system calls)
  #   dangerous       -> requires user approval (shell execution, unclassified tools)
  #
  # Each tool group has a default_hitl_category applied to all tools in that group.
  # To override a specific tool, add it to hitl_overrides.
  # Tools not found in any mapping default to dangerous (fail-closed).

  builtin_tools:
    filesystem:
      enabled: true
      default_hitl_category: read_only
      hitl_overrides:
        write_file: state_mutating  # file writes mutate state
    shell:
      enabled: true
      default_hitl_category: dangerous  # shell commands always require approval
    web_search:
      enabled: true
      default_hitl_category: read_only

  # MCP tools are dynamically loaded from external servers.
  # Default to dangerous since their behavior is unknown at config time.
  # Only override tools that have been verified as safe.
  mcp_default_category: dangerous
  mcp_overrides: {}
```

## Code Changes

### 1. ToolCategory Enum

New enum in `src/models/agent.py` (shared location — used by both config models and middleware):

```python
class ToolCategory(str, Enum):
    READ_ONLY = "read_only"
    STATE_MUTATING = "state_mutating"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"
```

### 2. Config Model Changes (`src/configs/agent/openai_chat_agent.py`)

Add `default_hitl_category` and `hitl_overrides` fields to each tool config model. Add `mcp_default_category` and `mcp_overrides` to the top-level agent config.

```python
class FileSystemToolConfig(BaseModel):
    enabled: bool = True
    default_hitl_category: ToolCategory = ToolCategory.READ_ONLY
    hitl_overrides: dict[str, ToolCategory] = {"write_file": ToolCategory.STATE_MUTATING}

class ShellToolConfig(BaseModel):
    enabled: bool = True
    default_hitl_category: ToolCategory = ToolCategory.DANGEROUS
    hitl_overrides: dict[str, ToolCategory] = {}

class WebSearchToolConfig(BaseModel):
    enabled: bool = True
    default_hitl_category: ToolCategory = ToolCategory.READ_ONLY
    hitl_overrides: dict[str, ToolCategory] = {}
```

Note: Pydantic V2 validates `ToolCategory` fields at config load time, so YAML typos (e.g., `readonly` instead of `read_only`) are caught at startup.

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

### 4. Category Map Assembly (`openai_chat_agent.initialize_async()`)

Build the complete `category_map` by merging layers:

```
_DEFAULT_CATEGORIES (ALL builtin tools — explicit name-to-category mapping)
  ↓ merge
YAML builtin_tools hitl_overrides (per-tool exceptions from config)
  ↓ merge
MCP tools → all set to mcp_default_category
  ↓ merge
YAML mcp_overrides (per-tool exceptions)
  = final category_map: dict[str, ToolCategory]
```

`_DEFAULT_CATEGORIES` is a module-level constant that explicitly maps **every** builtin tool name to its category. This avoids the need to discover tool names from groups at runtime — the mapping is authoritative and complete. When adding a new tool, add its entry here; if omitted, the fail-closed default (`DANGEROUS`) applies.

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
class HitLRequestMessage(BaseMessage):
    type: MessageType = MessageType.HITL_REQUEST
    request_id: str
    tool_name: str
    tool_args: dict
    session_id: str
    category: ToolCategory
```

Note: `HitLRequestMessage` is currently defined as a schema reference but not instantiated in the WebSocket pipeline. Events flow as raw dicts from `_consume_astream` through to the client. The model change serves as schema documentation and for any future pipeline refactoring that uses Pydantic serialization.

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
    "category": interrupt_value["category"],
}
```

### 7. No Changes Required

- `HitLResponseMessage` — unchanged (`approved: bool` only)
- WebSocket routing — unchanged
- `handle_hitl_response()` — unchanged
- `resume_after_approval()` — unchanged

## Test Strategy

### Unit Tests (modify existing + add new)

**`test_hitl_middleware.py`:**
- Refactor existing `is_dangerous()` tests → `get_category()` / `requires_approval()`
- `read_only` tool → bypass (no interrupt)
- `state_mutating` / `external` / `dangerous` tool → interrupt
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

### E2E Tests

- Existing approve/deny flows: verify `hitl_request` includes `category` field and value is valid `ToolCategory`
- Safe tool (e.g., `read_file`): no `hitl_request` emitted, executes directly

## Migration

No data migration needed. The change is purely in middleware logic and config schema. Existing YAML configs without `default_hitl_category` / `hitl_overrides` fields will use Pydantic defaults.

**Behavioral change from Phase 1:** In Phase 1, all non-MCP/non-delegate builtin tools auto-execute without approval. In Phase 2, `_DEFAULT_CATEGORIES` explicitly classifies every builtin tool. If a new tool is added but not registered in `_DEFAULT_CATEGORIES`, it will default to `dangerous` and require approval — this is intentional (fail-closed). Verify the complete tool list before deploying.
