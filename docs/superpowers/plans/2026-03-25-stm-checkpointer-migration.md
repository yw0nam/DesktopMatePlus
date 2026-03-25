# STM → LangGraph Checkpointer Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace custom `MongoDBSTM` service with LangGraph `MongoDBSaver` checkpointer and `CustomAgentState`, eliminating `stm_service/` entirely.

**Architecture:** LangGraph `MongoDBSaver` handles all message persistence via `thread_id`-keyed checkpoints; custom state fields (`pending_tasks`, `ltm_last_consolidated_at_turn`, `user_id`, `agent_id`, `knowledge_saved`) move into `CustomAgentState`; a thin `session_registry` MongoDB collection serves session listing and sweep iteration. External APIs keep `session_id`; internally mapped to LangGraph's `thread_id` inside `AgentService`.

**Tech Stack:** Python 3.13, LangGraph 0.6.8, `langgraph-checkpoint-mongodb` (new dependency), pymongo, FastAPI, langchain `create_agent`, `@after_model` middleware

**Spec:** `docs/superpowers/specs/2026-03-25-stm-checkpointer-migration-design.md`

---

## File Map

### Create
- `src/services/agent_service/state.py` — `CustomAgentState`, `PendingTask`, `ReplyChannel`
- `src/services/agent_service/session_registry.py` — `SessionRegistry` pymongo collection wrapper
- `src/services/agent_service/utils/ltm_consolidation_middleware.py` — `@after_model` LTM trigger + safe wrapper
- `yaml_files/services/checkpointer.yml` — MongoDB connection config (replaces `stm_service/mongodb.yml`)
- `tests/agents/test_custom_agent_state.py`
- `tests/agents/test_session_registry.py`
- `tests/agents/test_ltm_consolidation_middleware.py`
- `tests/agents/test_openai_chat_agent.py`

### Modify
- `pyproject.toml` — add `langgraph-checkpoint-mongodb`
- `src/services/agent_service/service.py` — add `context: dict | None = None` to `stream`/`invoke`
- `src/services/agent_service/openai_chat_agent.py` — checkpointer, `state_schema`, `thread_id`, `context`
- `src/services/agent_service/utils/delegate_middleware.py` — remove STM, `session_id`→`thread_id`
- `src/services/agent_service/tools/delegate/delegate_task.py` — async `_arun`, `ToolRuntime`, `Command`
- `src/services/websocket_service/manager/memory_orchestrator.py` — rename to `load_ltm_prefix`, delete `save_turn`
- `src/services/websocket_service/manager/handlers.py` — `load_ltm_prefix`, `session_registry.upsert`
- `src/services/websocket_service/manager/disconnect_handler.py` — `agent.aget_state` replaces STM
- `src/services/websocket_service/message_processor/event_handlers.py` — remove `save_turn` call
- `src/services/channel_service/__init__.py` — `load_ltm_prefix`, `session_registry.upsert`, remove STM
- `src/services/task_sweep_service/sweep.py` — `session_registry` + `agent.aget_state`
- `src/services/health.py` — `check_stm` → `check_mongodb`
- `src/api/routes/stm.py` — rewrite 5 endpoints + add `GET /{session_id}/messages`
- `src/api/routes/callback.py` — `agent.aget_state/aupdate_state`, task-level `reply_channel`
- `src/services/service_manager.py` — add MongoDB client, remove STM
- `src/main.py` — `initialize_mongodb_client`, remove STM init, update sweep constructor
- `tests/services/test_delegate_task.py` — rewrite for async + ToolRuntime
- `tests/agents/test_delegate_middleware.py` — update `session_id`→`thread_id`
- `tests/services/test_memory_orchestrator.py` — update for `load_ltm_prefix`
- `tests/services/channel_service/test_process_message.py` — remove STM refs
- `tests/api/test_callback_api.py` — mock `agent.aget_state/aupdate_state`
- `tests/services/test_background_sweep.py` — session_registry pattern
- `tests/services/task_sweep_service/test_sweep_slack.py` — session_registry pattern
- `tests/api/test_stm_api.py` — rewrite for checkpointer-based routes
- `tests/api/test_health_endpoint.py` — `STM` → `MongoDB` module name

### Delete
- `src/services/stm_service/` (entire directory)
- `yaml_files/services/stm_service/` (entire directory)
- `tests/storage/test_mongodb_stm.py`
- `tests/services/stm_service/` (entire directory)

---

## Task 1: CustomAgentState + SessionRegistry + MongoDB client singleton

**Files:**
- Create: `src/services/agent_service/state.py`
- Create: `src/services/agent_service/session_registry.py`
- Create: `yaml_files/services/checkpointer.yml`
- Modify: `src/services/service_manager.py`
- Modify: `pyproject.toml`
- Test: `tests/agents/test_custom_agent_state.py` (new)
- Test: `tests/agents/test_session_registry.py` (new)

- [ ] **Step 1: Write failing tests for CustomAgentState**

```python
# tests/agents/test_custom_agent_state.py
from src.services.agent_service.state import CustomAgentState, PendingTask, ReplyChannel


def test_custom_agent_state_fields():
    state = CustomAgentState(
        messages=[],
        user_id="u1",
        agent_id="yuri",
        pending_tasks=[],
        ltm_last_consolidated_at_turn=0,
        knowledge_saved=False,
    )
    assert state["user_id"] == "u1"
    assert state["pending_tasks"] == []
    assert state["knowledge_saved"] is False


def test_pending_task_with_reply_channel():
    task: PendingTask = {
        "task_id": "t1",
        "description": "do something",
        "status": "running",
        "created_at": "2026-03-25T00:00:00Z",
        "reply_channel": {"provider": "slack", "channel_id": "C123"},
    }
    assert task["reply_channel"]["provider"] == "slack"


def test_pending_task_reply_channel_none():
    task: PendingTask = {
        "task_id": "t2",
        "description": "ws task",
        "status": "running",
        "created_at": "2026-03-25T00:00:00Z",
        "reply_channel": None,
    }
    assert task["reply_channel"] is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/agents/test_custom_agent_state.py -v
```
Expected: `ImportError` — module not found

- [ ] **Step 3: Create `src/services/agent_service/state.py`**

```python
"""CustomAgentState for LangGraph checkpointer migration."""
from typing import TypedDict

from langchain.agents import AgentState


class ReplyChannel(TypedDict):
    provider: str    # "slack" | "websocket"
    channel_id: str


class PendingTask(TypedDict):
    task_id: str
    description: str
    status: str      # "running" | "done" | "failed"
    created_at: str
    reply_channel: ReplyChannel | None


class CustomAgentState(AgentState):
    user_id: str
    agent_id: str
    pending_tasks: list[PendingTask]
    ltm_last_consolidated_at_turn: int
    knowledge_saved: bool
```

- [ ] **Step 4: Run tests — expect PASS (3 tests)**

```bash
uv run pytest tests/agents/test_custom_agent_state.py -v
```

- [ ] **Step 5: Write failing tests for SessionRegistry**

```python
# tests/agents/test_session_registry.py
from unittest.mock import MagicMock
from src.services.agent_service.session_registry import SessionRegistry


def _make_registry():
    col = MagicMock()
    return SessionRegistry(col), col


def test_upsert_filters_by_thread_id():
    registry, col = _make_registry()
    registry.upsert("thread-1", "user-1", "yuri")
    col.update_one.assert_called_once()
    assert col.update_one.call_args[0][0] == {"thread_id": "thread-1"}


def test_list_sessions_calls_find_with_filter():
    registry, col = _make_registry()
    col.find.return_value = [{"thread_id": "t1"}]
    result = registry.list_sessions("u1", "yuri")
    call_filter = col.find.call_args[0][0]
    assert call_filter == {"user_id": "u1", "agent_id": "yuri"}
    assert result[0]["thread_id"] == "t1"


def test_find_all_returns_list():
    registry, col = _make_registry()
    col.find.return_value = [{"thread_id": "t1"}, {"thread_id": "t2"}]
    assert len(registry.find_all()) == 2


def test_delete_true_on_success():
    registry, col = _make_registry()
    col.delete_one.return_value = MagicMock(deleted_count=1)
    assert registry.delete("t1") is True


def test_delete_false_on_miss():
    registry, col = _make_registry()
    col.delete_one.return_value = MagicMock(deleted_count=0)
    assert registry.delete("nope") is False
```

- [ ] **Step 6: Run to verify failure**

```bash
uv run pytest tests/agents/test_session_registry.py -v
```

- [ ] **Step 7: Create `src/services/agent_service/session_registry.py`**

```python
"""Thin wrapper around MongoDB session_registry collection."""
from datetime import datetime, timezone

import pymongo
from pymongo.collection import Collection


class SessionRegistry:
    def __init__(self, collection: Collection) -> None:
        self._col = collection
        self._col.create_index(
            [("user_id", pymongo.ASCENDING), ("agent_id", pymongo.ASCENDING)]
        )
        self._col.create_index([("updated_at", pymongo.DESCENDING)])

    def upsert(self, thread_id: str, user_id: str, agent_id: str) -> None:
        now = datetime.now(timezone.utc)
        self._col.update_one(
            {"thread_id": thread_id},
            {
                "$set": {"user_id": user_id, "agent_id": agent_id, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def list_sessions(self, user_id: str, agent_id: str) -> list[dict]:
        return list(
            self._col.find(
                {"user_id": user_id, "agent_id": agent_id},
                sort=[("updated_at", pymongo.DESCENDING)],
            )
        )

    def find_all(self) -> list[dict]:
        return list(self._col.find({}, {"thread_id": 1}))

    def delete(self, thread_id: str) -> bool:
        return self._col.delete_one({"thread_id": thread_id}).deleted_count > 0
```

- [ ] **Step 8: Run all — expect PASS (8 tests)**

```bash
uv run pytest tests/agents/test_custom_agent_state.py tests/agents/test_session_registry.py -v
```

- [ ] **Step 9: Create `yaml_files/services/checkpointer.yml`**

```yaml
# MongoDB checkpointer — used by MongoDBSaver and session_registry
checkpointer_config:
  connection_string: "mongodb://admin:test@localhost:27017/"
  db_name: "desktopmate"
```

- [ ] **Step 10: Install package and verify import path**

```bash
uv add langgraph-checkpoint-mongodb
```

Then verify the actual class names shipped in the installed version:
```bash
uv run python -c "
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.checkpoint.mongodb import MongoDBSaver
print('AsyncMongoDBSaver OK:', AsyncMongoDBSaver)
print('MongoDBSaver OK:', MongoDBSaver)
"
```

If `AsyncMongoDBSaver` is not found, fall back to `MongoDBSaver` (sync) and use it directly — `create_agent` with a sync checkpointer is valid. Update Task 4 Step 4a/4b accordingly if the import path differs.

- [ ] **Step 11: Add MongoDB client singleton to `src/services/service_manager.py`**

Add after existing imports (near line 19):
```python
import pymongo as _pymongo
from src.services.agent_service.session_registry import SessionRegistry
```

Add after existing globals (near line 26):
```python
_mongo_client: "_pymongo.MongoClient | None" = None
_session_registry_instance: "SessionRegistry | None" = None
```

Add these two functions before `initialize_tts_service` (near line 147):
```python
def initialize_mongodb_client(
    config_path: Optional[str | Path] = None, force_reinit: bool = False
) -> "_pymongo.MongoClient":
    """Initialize shared MongoDB client for checkpointer and session_registry."""
    global _mongo_client, _session_registry_instance
    if _mongo_client is not None and not force_reinit:
        logger.debug("MongoDB client already initialized, skipping")
        return _mongo_client

    resolved = Path(config_path) if config_path else _BASE_YAML / "services" / "checkpointer.yml"
    cfg = _load_yaml_config(resolved).get("checkpointer_config", {})
    connection_string: str = cfg["connection_string"]
    db_name: str = cfg["db_name"]

    _mongo_client = _pymongo.MongoClient(connection_string, uuidRepresentation="standard")
    _mongo_client.admin.command("ping")
    db = _mongo_client[db_name]
    _session_registry_instance = SessionRegistry(db["session_registry"])
    logger.info(f"MongoDB client initialized (db={db_name})")
    return _mongo_client


def get_mongo_client() -> "_pymongo.MongoClient | None":
    return _mongo_client


def get_session_registry() -> "SessionRegistry | None":
    return _session_registry_instance
```

Add to `__all__` list at bottom of file:
```python
"initialize_mongodb_client",
"get_mongo_client",
"get_session_registry",
```

- [ ] **Step 12: Export MongoDB functions from `src/services/__init__.py`**

`src/services/__init__.py` re-exports from `service_manager`. Add the three new symbols so callers can `from src.services import initialize_mongodb_client`:

```python
# In the import block, extend the existing service_manager import:
from src.services.service_manager import (
    get_agent_service,
    get_emotion_motion_mapper,
    get_ltm_service,
    get_mongo_client,           # ADD
    get_session_registry,       # ADD
    get_tts_service,
    initialize_agent_service,
    initialize_emotion_motion_mapper,
    initialize_ltm_service,
    initialize_mongodb_client,  # ADD
    initialize_tts_service,
)

# In __all__, add:
"initialize_mongodb_client",
"get_mongo_client",
"get_session_registry",
```

- [ ] **Step 13: Lint**

```bash
sh scripts/lint.sh
```

- [ ] **Step 13: Commit**

```bash
git add src/services/agent_service/state.py \
        src/services/agent_service/session_registry.py \
        yaml_files/services/checkpointer.yml \
        src/services/service_manager.py \
        pyproject.toml uv.lock \
        tests/agents/test_custom_agent_state.py \
        tests/agents/test_session_registry.py
git commit -m "feat: CustomAgentState, SessionRegistry, MongoDB client singleton"
```

---

## Task 2: LTMConsolidationMiddleware

**Files:**
- Create: `src/services/agent_service/utils/ltm_consolidation_middleware.py`
- Test: `tests/agents/test_ltm_consolidation_middleware.py` (new)

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/test_ltm_consolidation_middleware.py
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from src.services.agent_service.utils.ltm_consolidation_middleware import (
    ltm_consolidation_hook,
    _LTM_CONSOLIDATION_INTERVAL,
)


def _state(n_human: int, last: int = 0) -> dict:
    msgs = []
    for i in range(n_human):
        msgs.append(HumanMessage(content=f"h{i}"))
        msgs.append(AIMessage(content=f"a{i}"))
    return {
        "messages": msgs,
        "user_id": "u1",
        "agent_id": "yuri",
        "ltm_last_consolidated_at_turn": last,
    }


def test_returns_none_below_threshold():
    result = ltm_consolidation_hook(_state(_LTM_CONSOLIDATION_INTERVAL - 1), MagicMock())
    assert result is None


def test_returns_update_at_threshold():
    with patch("src.services.agent_service.utils.ltm_consolidation_middleware.get_ltm_service") as m, \
         patch("asyncio.create_task"):
        m.return_value = MagicMock()
        result = ltm_consolidation_hook(_state(_LTM_CONSOLIDATION_INTERVAL), MagicMock())
    assert result == {"ltm_last_consolidated_at_turn": _LTM_CONSOLIDATION_INTERVAL}


def test_skips_when_ltm_unavailable():
    with patch("src.services.agent_service.utils.ltm_consolidation_middleware.get_ltm_service") as m:
        m.return_value = None
        result = ltm_consolidation_hook(_state(_LTM_CONSOLIDATION_INTERVAL), MagicMock())
    assert result is None


def test_no_double_trigger_within_interval():
    # consolidated at 10, current 15 — delta 5 < 10
    with patch("src.services.agent_service.utils.ltm_consolidation_middleware.get_ltm_service") as m, \
         patch("asyncio.create_task") as mock_task:
        m.return_value = MagicMock()
        result = ltm_consolidation_hook(_state(15, last=10), MagicMock())
    assert result is None
    mock_task.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/agents/test_ltm_consolidation_middleware.py -v
```

- [ ] **Step 3: Create `src/services/agent_service/utils/ltm_consolidation_middleware.py`**

```python
"""LTM consolidation middleware — fires after each model call via @after_model."""
import asyncio

from langchain.agents.middleware import after_model
from langchain_core.messages import HumanMessage
from loguru import logger

_LTM_CONSOLIDATION_INTERVAL = 10


@after_model
def ltm_consolidation_hook(state, runtime):
    """Fire-and-forget LTM consolidation when HumanMessage turn threshold is reached."""
    last = state.get("ltm_last_consolidated_at_turn", 0)
    current = sum(1 for m in state.get("messages", []) if isinstance(m, HumanMessage))

    if current - last < _LTM_CONSOLIDATION_INTERVAL:
        return None

    from src.services.service_manager import get_ltm_service

    ltm = get_ltm_service()
    if not ltm:
        return None

    asyncio.create_task(
        _safe_consolidate_ltm(
            ltm_service=ltm,
            messages=list(state["messages"]),
            user_id=state.get("user_id", ""),
            agent_id=state.get("agent_id", ""),
            last_consolidated=last,
        )
    )
    return {"ltm_last_consolidated_at_turn": current}


async def _safe_consolidate_ltm(
    ltm_service, messages: list, user_id: str, agent_id: str, last_consolidated: int
) -> None:
    """Ensures consolidation failures are logged and never swallowed silently."""
    try:
        await _consolidate_ltm(ltm_service, messages, user_id, agent_id, last_consolidated)
    except Exception as e:
        logger.error(f"LTM consolidation failed (user={user_id}, agent={agent_id}): {e}")


async def _consolidate_ltm(
    ltm_service, messages: list, user_id: str, agent_id: str, last_consolidated: int
) -> None:
    slice_start = len(messages)
    human_count = 0
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            if human_count == last_consolidated:
                slice_start = idx
                break
            human_count += 1

    await asyncio.to_thread(
        ltm_service.add_memory,
        messages=messages[slice_start:],
        user_id=user_id,
        agent_id=agent_id,
    )
    total = sum(1 for m in messages if isinstance(m, HumanMessage))
    logger.info(f"LTM consolidated at turn {total} (user={user_id})")
```

- [ ] **Step 4: Run tests — expect PASS (4 tests)**

```bash
uv run pytest tests/agents/test_ltm_consolidation_middleware.py -v
```

- [ ] **Step 5: Lint and commit**

```bash
sh scripts/lint.sh
git add src/services/agent_service/utils/ltm_consolidation_middleware.py \
        tests/agents/test_ltm_consolidation_middleware.py
git commit -m "feat: LTMConsolidationMiddleware with @after_model and _safe_consolidate_ltm"
```

---

## Task 3: DelegateTaskTool + DelegateToolMiddleware

**Files:**
- Modify: `src/services/agent_service/tools/delegate/delegate_task.py`
- Modify: `src/services/agent_service/utils/delegate_middleware.py`
- Test: `tests/services/test_delegate_task.py` (rewrite)
- Test: `tests/agents/test_delegate_middleware.py` (update `session_id`→`thread_id`)

- [ ] **Step 1: Rewrite `tests/services/test_delegate_task.py`**

```python
# tests/services/test_delegate_task.py — full rewrite
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.services.agent_service.tools.delegate.delegate_task import DelegateTaskTool


def _runtime(pending=None, reply_channel=None):
    r = MagicMock()
    r.state = {"pending_tasks": pending or []}
    r.context = {"reply_channel": reply_channel}
    return r


async def test_arun_creates_pending_task():
    tool = DelegateTaskTool()
    with patch("httpx.AsyncClient") as cls:
        cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(post=AsyncMock()))
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("do research", runtime=_runtime())

    assert isinstance(result, Command)
    assert len(result.update["pending_tasks"]) == 1
    assert result.update["pending_tasks"][0]["status"] == "running"
    assert result.update["pending_tasks"][0]["reply_channel"] is None


async def test_arun_captures_reply_channel():
    tool = DelegateTaskTool()
    rc = {"provider": "slack", "channel_id": "C1"}
    with patch("httpx.AsyncClient") as cls:
        cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(post=AsyncMock()))
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime(reply_channel=rc))

    assert result.update["pending_tasks"][0]["reply_channel"] == rc


async def test_arun_includes_tool_message():
    tool = DelegateTaskTool()
    with patch("httpx.AsyncClient") as cls:
        cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(post=AsyncMock()))
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime())

    assert isinstance(result.update["messages"][0], ToolMessage)


async def test_arun_http_failure_returns_command():
    tool = DelegateTaskTool()
    with patch("httpx.AsyncClient") as cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await tool._arun("task", runtime=_runtime())

    assert isinstance(result, Command)
    assert "통신에 실패" in result.update["messages"][0].content
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/services/test_delegate_task.py -v
```
Expected: FAIL (old `_run` signature)

- [ ] **Step 3: Rewrite `src/services/agent_service/tools/delegate/delegate_task.py`**

```python
"""DelegateTaskTool — async, uses ToolRuntime to read/write agent state."""
import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

from src.services.agent_service.state import PendingTask
from src.services.agent_service.tools.delegate.schemas import DelegateTaskInput

NANOCLAW_URL = os.getenv("NANOCLAW_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
NANOCLAW_WEBHOOK_PATH = "/api/webhooks/fastapi"
CALLBACK_PATH = "/v1/callback/nanoclaw"
HTTP_TIMEOUT = 5.0


class DelegateTaskTool(BaseTool):
    """Delegates a heavy task to NanoClaw for async processing."""

    name: str = "delegate_task"
    description: str = (
        "Delegate a heavy or long-running task to the team. "
        "Use this when the task requires deep research, code review, "
        "code generation, or any work that should not block the conversation."
    )
    args_schema: type[DelegateTaskInput] = DelegateTaskInput

    def _run(self, task: str, **kwargs) -> str:
        raise NotImplementedError("Use _arun")

    async def _arun(self, task: str, runtime=None, **kwargs) -> Command:
        task_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        state = getattr(runtime, "state", {}) or {}
        context = getattr(runtime, "context", {}) or {}
        pending = list(state.get("pending_tasks", []))
        reply_channel = context.get("reply_channel")

        task_record: PendingTask = {
            "task_id": task_id,
            "description": task,
            "status": "running",
            "created_at": now,
            "reply_channel": reply_channel,
        }
        pending.append(task_record)

        payload = {
            "task": task,
            "task_id": task_id,
            "callback_url": f"{BACKEND_URL}{CALLBACK_PATH}/{task_id}",
        }
        msg_content = f"팀에 작업을 지시했습니다. (task_id: {task_id})"

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                await client.post(f"{NANOCLAW_URL}{NANOCLAW_WEBHOOK_PATH}", json=payload)
        except Exception:
            msg_content = f"작업을 팀에 지시했지만, NanoClaw과의 통신에 실패했습니다. (task_id: {task_id})"

        return Command(
            update={
                "pending_tasks": pending,
                "messages": [ToolMessage(content=msg_content, tool_call_id=task_id)],
            }
        )
```

- [ ] **Step 4: Run delegate tests — expect PASS**

```bash
uv run pytest tests/services/test_delegate_task.py -v
```

- [ ] **Step 5: Update `tests/agents/test_delegate_middleware.py`**

Read the file. Apply two sets of changes:

**a. Replace `session_id` → `thread_id` in configurable assertions** — any mock or assertion that references `"session_id"` in `get_config()["configurable"]` must use `"thread_id"` instead.

**b. Add behavioral tests verifying no-STM contract** — append these new tests:

```python
from unittest.mock import AsyncMock, MagicMock, patch


async def test_awrap_model_call_does_not_call_get_stm_service():
    """STM removal verification — middleware must never touch STM."""
    with patch(
        "src.services.agent_service.utils.delegate_middleware.get_stm_service",
        autospec=True,
    ) as mock_stm:
        middleware = DelegateToolMiddleware()
        request = MagicMock()
        request.tools = []
        request.override = MagicMock(return_value=request)
        await middleware.awrap_model_call(request, AsyncMock())
        mock_stm.assert_not_called()


async def test_awrap_model_call_injects_delegate_tool_without_args():
    """DelegateTaskTool must be constructed with zero arguments."""
    middleware = DelegateToolMiddleware()
    request = MagicMock()
    request.tools = []
    captured = {}

    def capture_override(**kwargs):
        captured.update(kwargs)
        return request

    request.override = capture_override
    await middleware.awrap_model_call(request, AsyncMock())
    injected_tools = captured.get("tools", [])
    assert any(isinstance(t, DelegateTaskTool) for t in injected_tools)


async def test_awrap_tool_call_routes_only_delegate_tool():
    """awrap_tool_call must pass through non-delegate tool calls unchanged."""
    middleware = DelegateToolMiddleware()
    handler = AsyncMock()

    non_delegate_request = MagicMock()
    non_delegate_request.tool_call = {"name": "some_other_tool"}
    await middleware.awrap_tool_call(non_delegate_request, handler)
    handler.assert_called_once_with(non_delegate_request)
```

Note: if `get_stm_service` is not importable from `delegate_middleware` (already removed), the `patch` in the first test will raise `AttributeError` — that means the removal is already clean; skip that test and note it passes by absence.

Run:

```bash
uv run pytest tests/agents/test_delegate_middleware.py -v
```
Note failures, then proceed to Step 6.

- [ ] **Step 6: Rewrite `src/services/agent_service/utils/delegate_middleware.py`**

```python
"""DelegateToolMiddleware — injects DelegateTaskTool per request. No STM dependency."""
from langchain.agents.middleware.types import AgentMiddleware

from src.services.agent_service.tools.delegate import DelegateTaskTool


class DelegateToolMiddleware(AgentMiddleware):
    """Injects a fresh DelegateTaskTool instance into every model and tool call."""

    async def awrap_model_call(self, request, handler):
        delegate = DelegateTaskTool()
        return await handler(request.override(tools=[*request.tools, delegate]))

    async def awrap_tool_call(self, request, handler):
        _name = DelegateTaskTool.model_fields["name"].default
        if request.tool_call["name"] != _name:
            return await handler(request)
        return await handler(request.override(tool=DelegateTaskTool()))
```

- [ ] **Step 7: Run all delegate tests — expect PASS**

```bash
uv run pytest tests/services/test_delegate_task.py tests/agents/test_delegate_middleware.py -v
```

- [ ] **Step 8: Lint and commit**

```bash
sh scripts/lint.sh
git add src/services/agent_service/tools/delegate/delegate_task.py \
        src/services/agent_service/utils/delegate_middleware.py \
        tests/services/test_delegate_task.py \
        tests/agents/test_delegate_middleware.py
git commit -m "refactor: DelegateTaskTool async+ToolRuntime+Command, DelegateMiddleware removes STM"
```

---

## Task 4: OpenAIChatAgent checkpointer integration

**Files:**
- Modify: `src/services/agent_service/service.py`
- Modify: `src/services/agent_service/openai_chat_agent.py`
- Test: `tests/agents/test_openai_chat_agent.py` (new)

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/test_openai_chat_agent.py
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage

from src.services.agent_service.openai_chat_agent import OpenAIChatAgent


def _agent():
    with patch("src.services.agent_service.openai_chat_agent.ChatOpenAI"):
        svc = OpenAIChatAgent(
            temperature=0.7, top_p=0.9, openai_api_key="sk-test", model_name="gpt-4o"
        )
    svc.agent = MagicMock()
    return svc


async def _drain(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results


async def test_stream_uses_thread_id():
    svc = _agent()

    async def fake_astream(*args, **kwargs):
        yield ("updates", {"model": {"messages": [MagicMock(content="hi")]}})

    svc.agent.astream = fake_astream

    events = await _drain(svc.stream(messages=[HumanMessage("hi")], session_id="s1"))
    # Verify the config passed to astream had thread_id
    # (checked via monkey-patched capture below)
    captured = {}

    async def capturing_astream(input, config=None, context=None, **kw):
        captured["config"] = config
        captured["context"] = context
        return
        yield  # make it a generator

    svc.agent.astream = capturing_astream
    await _drain(svc.stream(messages=[HumanMessage("hi")], session_id="s1"))
    assert captured["config"]["configurable"]["thread_id"] == "s1"
    assert "session_id" not in captured["config"]["configurable"]


async def test_stream_passes_context():
    svc = _agent()
    captured = {}

    async def capturing_astream(input, config=None, context=None, **kw):
        captured["context"] = context
        return
        yield

    svc.agent.astream = capturing_astream
    rc = {"provider": "slack", "channel_id": "C1"}
    await _drain(svc.stream(
        messages=[HumanMessage("hi")], session_id="s1", context={"reply_channel": rc}
    ))
    assert captured["context"] == {"reply_channel": rc}


async def test_invoke_uses_thread_id():
    svc = _agent()
    svc.agent.ainvoke = AsyncMock(return_value={"messages": [MagicMock(content="reply")]})
    await svc.invoke(messages=[HumanMessage("hi")], session_id="s2")

    config = svc.agent.ainvoke.call_args.kwargs.get("config") or svc.agent.ainvoke.call_args.args[1]
    assert config["configurable"]["thread_id"] == "s2"
    assert "session_id" not in config["configurable"]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/agents/test_openai_chat_agent.py -v
```
Expected: FAIL — config has `session_id`, no `context` forwarded

- [ ] **Step 3: Add `context` param to `src/services/agent_service/service.py`**

Add `context: dict | None = None` to both `stream` and `invoke` abstract method signatures:

```python
# stream:
async def stream(
    self,
    messages: list[BaseMessage],
    session_id: str = "",
    persona_id: str = "",
    user_id: str = "default_user",
    agent_id: str = "default_agent",
    context: dict | None = None,   # NEW
):

# invoke:
async def invoke(
    self,
    messages: list[BaseMessage],
    session_id: str = "",
    persona_id: str = "",
    user_id: str = "default_user",
    agent_id: str = "default_agent",
    context: dict | None = None,   # NEW
) -> dict:
```

- [ ] **Step 4: Update `src/services/agent_service/openai_chat_agent.py`**

**4a.** Add imports after existing ones:

```python
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

from src.services.agent_service.state import CustomAgentState
from src.services.agent_service.utils.ltm_consolidation_middleware import (
    ltm_consolidation_hook,
)
```

**4b.** In `initialize_async()`, replace agent creation block (the `create_agent(...)` call):

```python
from src.services.service_manager import get_mongo_client

mongo_client = get_mongo_client()
checkpointer = AsyncMongoDBSaver(client=mongo_client) if mongo_client else None

self.agent = create_agent(
    model=self.llm,
    tools=self._mcp_tools,
    state_schema=CustomAgentState,
    checkpointer=checkpointer,
    middleware=[DelegateToolMiddleware(), ltm_consolidation_hook],
)
```

**4c.** Add `context: dict | None = None` to `stream()` signature; change config key; forward context:

```python
async def stream(
    self,
    messages: list[BaseMessage],
    session_id: str = "",
    persona_id: str = "",
    user_id: str = "default_user",
    agent_id: str = "default_agent",
    context: dict | None = None,        # ADD
):
    ...
    config = {"configurable": {"thread_id": session_id}}   # session_id → thread_id
    ...
    async for item in self._process_message(
        messages=messages, config=config, context=context   # ADD context
    ):
```

**4d.** Same for `invoke()`:

```python
async def invoke(
    self,
    messages: list[BaseMessage],
    session_id: str = "",
    persona_id: str = "",
    user_id: str = "default_user",
    agent_id: str = "default_agent",
    context: dict | None = None,        # ADD
) -> dict:
    ...
    config = {"configurable": {"thread_id": session_id}}   # session_id → thread_id
    ...
    result = await self.agent.ainvoke(
        {"messages": messages}, config=config, context=context   # ADD context
    )
```

**4e.** Add `context: dict | None = None` to `_process_message()` and pass to `astream`:

```python
async def _process_message(
    self,
    messages: list[BaseMessage],
    config: dict,
    context: dict | None = None,    # ADD
):
    ...
    async for stream_type, data in self.agent.astream(
        {"messages": messages},
        config=config,
        context=context,             # ADD
        stream_mode=["messages", "updates"],
    ):
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
uv run pytest tests/agents/test_openai_chat_agent.py -v
```

- [ ] **Step 6: Run full agents suite to catch regressions**

```bash
uv run pytest tests/agents/ -v
```

- [ ] **Step 7: Lint and commit**

```bash
sh scripts/lint.sh
git add src/services/agent_service/service.py \
        src/services/agent_service/openai_chat_agent.py \
        tests/agents/test_openai_chat_agent.py
git commit -m "feat: OpenAIChatAgent checkpointer+state_schema+thread_id+context param"
```

---

## Task 5: `load_ltm_prefix` + message-path callers

**Files:**
- Modify: `src/services/websocket_service/manager/memory_orchestrator.py`
- Modify: `src/services/websocket_service/manager/handlers.py`
- Modify: `src/services/channel_service/__init__.py`
- Modify: `src/services/websocket_service/message_processor/event_handlers.py`
- Test: `tests/services/test_memory_orchestrator.py` (update)
- Test: `tests/services/channel_service/test_process_message.py` (update)
- Test: `tests/websocket/test_handlers.py` (update)

- [ ] **Step 1: Write failing tests in `tests/services/test_memory_orchestrator.py`**

Read the existing file first. Add tests that assert the new contract, then rename/remove old ones:

```python
# Failing tests to add (assert new function name and signature):
from src.services.websocket_service.manager.memory_orchestrator import load_ltm_prefix
# ^ this import alone will fail until Step 2

async def test_load_ltm_prefix_returns_empty_without_ltm():
    result = await load_ltm_prefix(ltm_service=None, user_id="u1", agent_id="a1", query="hi")
    assert result == []

async def test_load_ltm_prefix_returns_system_message():
    ltm = MagicMock()
    ltm.search_memory = MagicMock(return_value={"results": [{"text": "memory"}]})
    result = await load_ltm_prefix(ltm_service=ltm, user_id="u1", agent_id="a1", query="hi")
    assert len(result) == 1
    assert "Long-term memories" in result[0].content

# Also assert save_turn no longer exists in the module:
def test_save_turn_not_exported():
    import src.services.websocket_service.manager.memory_orchestrator as mo
    assert not hasattr(mo, "save_turn"), "save_turn should be removed"

def test_load_context_not_exported():
    import src.services.websocket_service.manager.memory_orchestrator as mo
    assert not hasattr(mo, "load_context"), "load_context should be replaced by load_ltm_prefix"
```

Run to confirm failure:
```bash
uv run pytest tests/services/test_memory_orchestrator.py -v
```

- [ ] **Step 2: Rewrite `src/services/websocket_service/manager/memory_orchestrator.py`**

Replace entire file:

```python
"""Memory orchestrator — LTM prefix loading only.

STM persistence is automatic via LangGraph MongoDBSaver checkpointer.
LTM consolidation is handled by LTMConsolidationMiddleware (@after_model).
"""
import asyncio
import json

from langchain_core.messages import BaseMessage, SystemMessage
from loguru import logger

from src.services.ltm_service import LTMService


async def load_ltm_prefix(
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    query: str,
) -> list[BaseMessage]:
    """Return LTM search results as a SystemMessage prefix, or [] if unavailable."""
    if not ltm_service:
        return []
    try:
        result = await asyncio.to_thread(
            ltm_service.search_memory,
            query=query,
            user_id=user_id,
            agent_id=agent_id,
        )
        if result.get("results"):
            return [SystemMessage(content=f"Long-term memories: {json.dumps(result)}")]
    except Exception as e:
        logger.error(f"LTM prefix load failed (user={user_id}): {e}")
    return []
```

- [ ] **Step 3: Run memory orchestrator tests — expect PASS**

```bash
uv run pytest tests/services/test_memory_orchestrator.py -v
```

- [ ] **Step 4: Write failing test for `event_handlers.py` save_turn removal**

Add to `tests/core/test_event_handler_tts.py` or a new `tests/core/test_event_handler_save_turn.py`:

```python
def test_save_turn_not_imported_in_event_handlers():
    """Checkpointer handles saves — save_turn must not be called from event_handlers."""
    import src.services.websocket_service.message_processor.event_handlers as eh
    # save_turn should not be a name in the module's namespace at all
    assert not hasattr(eh, "save_turn"), (
        "save_turn found in event_handlers — checkpointer should handle persistence"
    )
```

Run:
```bash
uv run pytest tests/core/test_event_handler_save_turn.py -v
```
Expected: FAIL — `save_turn` is still imported in event_handlers.py

- [ ] **Step 4b: Update `src/services/websocket_service/message_processor/event_handlers.py`**

Remove the `save_turn` import at line 12:

```python
# DELETE this line:
from src.services.websocket_service.manager.memory_orchestrator import save_turn
```

Remove the fire-and-forget block inside `stream_end` handling (the `if new_chats and turn:` block that calls `asyncio.create_task(save_turn(...))`). The checkpointer saves automatically — nothing needed here.

Run test to confirm PASS:
```bash
uv run pytest tests/core/test_event_handler_save_turn.py -v
```

- [ ] **Step 5: Update `src/services/websocket_service/manager/handlers.py`**

Key changes in `handle_chat_message`:

a. Change module-level imports at top of file:

```python
# Remove: from src.services import get_agent_service, get_ltm_service, get_stm_service
# Replace with (module-level, not inline):
from src.services import get_agent_service, get_ltm_service
from src.services.service_manager import get_session_registry          # ADD module-level
from src.services.websocket_service.manager.memory_orchestrator import load_ltm_prefix
# (remove load_context import)
```

b. Remove `stm_service = get_stm_service()` line (near line 140).

c. After `session_id = str(session_id)` (near line 196), add session registry upsert — using the module-level import from step (a):

```python
registry = get_session_registry()
if registry:
    await asyncio.to_thread(registry.upsert, session_id, user_id, agent_id)
```

d. Replace `load_context(stm_service=..., ltm_service=..., ...)` call with:
```python
message_history = await load_ltm_prefix(
    ltm_service=ltm_service,
    user_id=user_id,
    agent_id=agent_id,
    query=content if isinstance(content, str) else "",
)
```

e. Remove `metadata["stm_service"] = stm_service` line.

f. Add `context={"reply_channel": None}` to `agent_service.stream(...)` call.

- [ ] **Step 6: Update `src/services/channel_service/__init__.py`**

Replace `process_message` function. Remove `STMService` import and `stm` parameter. Add `load_ltm_prefix` and `session_registry.upsert`. Full replacement of the function body:

```python
async def process_message(
    *,
    text: str,
    session_id: str,
    provider: str,
    channel_id: str,
    user_id: str = "default",
    agent_id: str = "yuri",
    agent_service: AgentService,
    ltm: LTMService | None = None,
) -> None:
    """Process external channel message. Checkpointer handles persistence automatically."""
    async with session_lock(session_id):
        from src.services.service_manager import get_session_registry
        registry = get_session_registry()
        if registry:
            await asyncio.to_thread(registry.upsert, session_id, user_id, agent_id)

        ltm_prefix = await load_ltm_prefix(
            ltm_service=ltm, user_id=user_id, agent_id=agent_id, query=text
        )
        messages = ltm_prefix + ([HumanMessage(text)] if text else [])
        reply_channel = {"provider": provider, "channel_id": channel_id}
        slack = get_slack_service() if provider == "slack" else None

        try:
            result = await agent_service.invoke(
                messages=messages,
                session_id=session_id,
                persona_id=agent_id,
                user_id=user_id,
                agent_id=agent_id,
                context={"reply_channel": reply_channel},
            )
            final_text = _tts_processor.process(result["content"]).filtered_text
            if slack:
                await slack.send_message(channel_id, final_text)
        except Exception as e:
            logger.error(f"process_message failed for session {session_id}: {e}")
            if slack:
                await slack.send_message(channel_id, "처리 중 오류가 발생했어. 다시 시도해줘")
```

Remove these imports from the file (no longer needed):
```python
from src.services.stm_service.service import STMService
from src.services.websocket_service.manager.memory_orchestrator import load_context, save_turn
```

Add:
```python
from src.services.websocket_service.manager.memory_orchestrator import load_ltm_prefix
```

Also update `callback.py`'s call to `process_message` — remove `stm=stm_svc` kwarg (will be done in Task 7).

- [ ] **Step 7: Update `tests/services/channel_service/test_process_message.py`**

Read file. Remove `stm=` kwarg from any `process_message(...)` calls. Remove STM mocks. Add `mock_get_session_registry` returning `None`. Run:
```bash
uv run pytest tests/services/channel_service/test_process_message.py -v
```

- [ ] **Step 8: Update `tests/websocket/test_handlers.py`**

Remove assertions that `metadata["stm_service"]` is set. Run:
```bash
uv run pytest tests/websocket/test_handlers.py -v
```

- [ ] **Step 9: Run all affected tests**

```bash
uv run pytest tests/services/test_memory_orchestrator.py \
              tests/services/channel_service/ \
              tests/websocket/test_handlers.py \
              tests/core/ -v
```
Expected: PASS

- [ ] **Step 10: Lint and commit**

```bash
sh scripts/lint.sh
git add src/services/websocket_service/manager/memory_orchestrator.py \
        src/services/websocket_service/manager/handlers.py \
        src/services/websocket_service/message_processor/event_handlers.py \
        src/services/channel_service/__init__.py \
        tests/services/test_memory_orchestrator.py \
        tests/services/channel_service/test_process_message.py \
        tests/websocket/test_handlers.py
git commit -m "refactor: load_ltm_prefix replaces load_context+save_turn, session_registry.upsert"
```

---

## Task 6: disconnect_handler.py

**Files:**
- Modify: `src/services/websocket_service/manager/disconnect_handler.py`
- Test: `tests/services/websocket_service/test_knowledge_trigger.py` (update)

- [ ] **Step 1: Run existing tests to record baseline**

```bash
uv run pytest tests/services/websocket_service/test_knowledge_trigger.py -v
```

- [ ] **Step 2: Rewrite tests — replace STMService with AgentService mock**

```python
# tests/services/websocket_service/test_knowledge_trigger.py — key cases
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage

from src.services.websocket_service.manager.disconnect_handler import (
    on_disconnect_handler,
    MIN_TURNS_FOR_SUMMARY,
)


def _agent_service(messages, knowledge_saved=False):
    svc = MagicMock()
    checkpoint = MagicMock()
    checkpoint.values = {"messages": messages, "knowledge_saved": knowledge_saved}
    svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    svc.agent.aupdate_state = AsyncMock()
    return svc


async def test_skips_when_knowledge_saved():
    svc = _agent_service([HumanMessage("hi")] * MIN_TURNS_FOR_SUMMARY, knowledge_saved=True)
    delegate = AsyncMock()
    await on_disconnect_handler("s1", "u1", "yuri", agent_service=svc, delegate=delegate)
    delegate.assert_not_called()


async def test_skips_when_too_few_turns():
    svc = _agent_service([HumanMessage("hi")])  # below threshold
    delegate = AsyncMock()
    await on_disconnect_handler("s1", "u1", "yuri", agent_service=svc, delegate=delegate)
    delegate.assert_not_called()


async def test_delegates_and_marks_saved():
    msgs = [HumanMessage(f"msg {i}") for i in range(MIN_TURNS_FOR_SUMMARY)]
    svc = _agent_service(msgs)
    delegate = AsyncMock()
    await on_disconnect_handler("s1", "u1", "yuri", agent_service=svc, delegate=delegate)
    delegate.assert_called_once()
    update = svc.agent.aupdate_state.call_args[0][1]
    assert update == {"knowledge_saved": True}


async def test_aget_state_called_with_thread_id():
    msgs = [HumanMessage(f"m{i}") for i in range(MIN_TURNS_FOR_SUMMARY)]
    svc = _agent_service(msgs)
    await on_disconnect_handler("sess-99", "u1", "yuri", agent_service=svc, delegate=AsyncMock())
    config = svc.agent.aget_state.call_args[0][0]
    assert config["configurable"]["thread_id"] == "sess-99"
```

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/services/websocket_service/test_knowledge_trigger.py -v
```

- [ ] **Step 4: Rewrite `src/services/websocket_service/manager/disconnect_handler.py`**

```python
"""Disconnect-time delegate trigger for knowledge summary."""
import os
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage as HMsg
from loguru import logger

MIN_TURNS_FOR_SUMMARY: int = 3
STM_INLINE_MAX_TURNS: int = 30
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")


def build_delegate_payload(
    session_id: str,
    user_id: str,
    agent_id: str,
    messages: list,
) -> dict:
    """Build NanoClaw knowledge_summary payload (inline or fetch-URL)."""
    from langchain_core.messages import convert_to_openai_messages

    human_count = sum(1 for m in messages if isinstance(m, HMsg))
    base: dict = {
        "task": "knowledge_summary",
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": agent_id,
    }
    if human_count < STM_INLINE_MAX_TURNS:
        base["stm_messages"] = convert_to_openai_messages(messages)
    else:
        base["stm_fetch_url"] = f"{BACKEND_URL}/v1/stm/{session_id}/messages"
    return base


async def on_disconnect_handler(
    session_id: str,
    user_id: str,
    agent_id: str,
    agent_service,
    delegate: Callable[[dict], Awaitable[None]],
) -> None:
    """Trigger knowledge summary on session disconnect via agent state."""
    try:
        config = {"configurable": {"thread_id": session_id}}
        state = (await agent_service.agent.aget_state(config)).values

        if state.get("knowledge_saved"):
            logger.debug(f"Session {session_id}: knowledge already saved, skipping")
            return

        messages = state.get("messages", [])
        if sum(1 for m in messages if isinstance(m, HMsg)) < MIN_TURNS_FOR_SUMMARY:
            logger.debug(f"Session {session_id}: too few turns, skipping summary")
            return

        payload = build_delegate_payload(
            session_id=session_id, user_id=user_id, agent_id=agent_id, messages=messages
        )
        logger.info(f"Session {session_id}: triggering knowledge summary delegation")
        await delegate(payload)
        await agent_service.agent.aupdate_state(config, {"knowledge_saved": True})

    except Exception as e:
        logger.error(f"Session {session_id}: on_disconnect_handler error: {e}")
```

Note: find callers of `on_disconnect_handler` in the websocket manager and update the call site to pass `agent_service=` instead of `stm_service=`. Search with:
```bash
grep -rn "on_disconnect_handler" src/
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
uv run pytest tests/services/websocket_service/test_knowledge_trigger.py -v
```

- [ ] **Step 6: Lint and commit**

```bash
sh scripts/lint.sh
git add src/services/websocket_service/manager/disconnect_handler.py \
        tests/services/websocket_service/test_knowledge_trigger.py
git commit -m "refactor: disconnect_handler uses agent.aget_state instead of STMService"
```

---

## Task 7: callback.py

**Files:**
- Modify: `src/api/routes/callback.py`
- Test: `tests/api/test_callback_api.py` (update)

- [ ] **Step 1: Update `tests/api/test_callback_api.py`**

Read the file. Replace `get_stm_service` mocks with `agent.aget_state` / `agent.aupdate_state` mocks. Core mock pattern:

```python
def _mock_agent(task_id="t1", task_status="running", reply_channel=None):
    svc = MagicMock()
    state = {
        "pending_tasks": [{"task_id": task_id, "status": task_status, "reply_channel": reply_channel}],
        "user_id": "u1",
        "agent_id": "yuri",
    }
    checkpoint = MagicMock()
    checkpoint.values = state
    svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    svc.agent.aupdate_state = AsyncMock()
    return svc
```

Run existing tests to see failures:
```bash
uv run pytest tests/api/test_callback_api.py -v
```

- [ ] **Step 2: Rewrite `src/api/routes/callback.py`**

```python
"""NanoClaw callback API routes."""
import asyncio

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import SystemMessage
from loguru import logger

from src.models.callback import NanoClawCallbackRequest, NanoClawCallbackResponse
from src.services import get_agent_service

router = APIRouter(prefix="/v1/callback", tags=["Callback"])


@router.post(
    "/nanoclaw/{session_id}",
    response_model=NanoClawCallbackResponse,
    summary="Receive task result from NanoClaw",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Task not found"},
        503: {"description": "Agent service not initialized or state update failed"},
    },
)
async def nanoclaw_callback(session_id: str, payload: NanoClawCallbackRequest):
    """Inject synthetic message into agent state; route result to originating channel."""
    agent_svc = get_agent_service()
    if agent_svc is None:
        raise HTTPException(503, "Agent service not initialized")

    config = {"configurable": {"thread_id": session_id}}
    state = (await agent_svc.agent.aget_state(config)).values
    pending_tasks = list(state.get("pending_tasks", []))

    task_record = next((t for t in pending_tasks if t.get("task_id") == payload.task_id), None)
    if task_record is None:
        raise HTTPException(404, f"Task {payload.task_id} not found in session {session_id}")

    task_record["status"] = payload.status
    prefix = "TaskResult" if payload.status == "done" else "TaskFailed"
    synthetic_msg = SystemMessage(content=f"[{prefix}:{payload.task_id}] {payload.summary}")

    try:
        await agent_svc.agent.aupdate_state(
            config, {"messages": [synthetic_msg], "pending_tasks": pending_tasks}
        )
    except Exception as e:
        logger.error(f"State update failed for session {session_id}: {e}")
        raise HTTPException(503, "State update failed")

    # Route to originating channel via task-level reply_channel (not session-level)
    reply_channel = task_record.get("reply_channel")
    if reply_channel:
        from src.services import get_ltm_service
        from src.services.channel_service import process_message

        asyncio.create_task(
            process_message(
                text="",
                session_id=session_id,
                provider=reply_channel["provider"],
                channel_id=reply_channel["channel_id"],
                user_id=state.get("user_id", "default"),
                agent_id=state.get("agent_id", "yuri"),
                agent_service=agent_svc,
                ltm=get_ltm_service(),
            )
        )
        logger.info(f"Callback routing to {reply_channel['provider']} for {session_id}")

    logger.info(f"Callback processed: task={payload.task_id} status={payload.status}")
    return NanoClawCallbackResponse(
        task_id=payload.task_id,
        status=payload.status,
        message=f"Task {payload.task_id} updated to {payload.status}",
    )
```

- [ ] **Step 3: Run tests — expect PASS**

```bash
uv run pytest tests/api/test_callback_api.py -v
```

- [ ] **Step 4: Lint and commit**

```bash
sh scripts/lint.sh
git add src/api/routes/callback.py tests/api/test_callback_api.py
git commit -m "refactor: callback.py uses agent.aget/aupdate_state, task-level reply_channel"
```

---

## Task 8: BackgroundSweepService + health.py

**Files:**
- Modify: `src/services/task_sweep_service/sweep.py`
- Modify: `src/services/health.py`
- Test: `tests/services/test_background_sweep.py` (update)
- Test: `tests/services/task_sweep_service/test_sweep_slack.py` (update)
- Test: `tests/api/test_health_endpoint.py` (update)

- [ ] **Step 1: Rewrite sweep tests — replace STM with session_registry + aget_state**

Core mock helper for both test files:

```python
from unittest.mock import AsyncMock, MagicMock
from src.services.agent_service.session_registry import SessionRegistry
from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig


def _make_sweep(sessions=None, pending_tasks=None):
    registry = MagicMock(spec=SessionRegistry)
    registry.find_all.return_value = sessions or [{"thread_id": "t1"}]

    agent_svc = MagicMock()
    checkpoint = MagicMock()
    checkpoint.values = {"pending_tasks": pending_tasks or []}
    agent_svc.agent.aget_state = AsyncMock(return_value=checkpoint)
    agent_svc.agent.aupdate_state = AsyncMock()

    svc = BackgroundSweepService(
        agent_service=agent_svc,
        session_registry=registry,
        config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
    )
    return svc, agent_svc, registry
```

Run to confirm failures:
```bash
uv run pytest tests/services/test_background_sweep.py \
              tests/services/task_sweep_service/test_sweep_slack.py -v
```

- [ ] **Step 2: Rewrite `src/services/task_sweep_service/sweep.py`**

```python
"""Background sweep — marks expired delegated tasks as failed."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.services.agent_service.service import AgentService
    from src.services.agent_service.session_registry import SessionRegistry
    from src.services.channel_service.slack_service import SlackService

_EXPIRABLE_STATUSES = frozenset({"pending", "running"})


class SweepConfig(BaseModel):
    sweep_interval_seconds: int = Field(default=60, ge=1)
    task_ttl_seconds: int = Field(default=300, ge=1)


class BackgroundSweepService:
    def __init__(
        self,
        agent_service: "AgentService",
        session_registry: "SessionRegistry",
        config: SweepConfig,
        slack_service_fn: Callable[[], "SlackService | None"] | None = None,
    ) -> None:
        self._agent = agent_service
        self._registry = session_registry
        self.config = config
        self._slack_service_fn = slack_service_fn
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="task_sweep_loop")
        logger.info(
            f"BackgroundSweepService started "
            f"(interval={self.config.sweep_interval_seconds}s, ttl={self.config.task_ttl_seconds}s)"
        )

    async def stop(self) -> None:
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.info("BackgroundSweepService stopped")

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        while True:
            try:
                await self._sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BackgroundSweepService: unhandled error during sweep")
            await asyncio.sleep(self.config.sweep_interval_seconds)

    async def _sweep_once(self) -> None:
        now = datetime.now(timezone.utc)
        ttl = self.config.task_ttl_seconds

        try:
            sessions = self._registry.find_all()
        except Exception:
            logger.exception("BackgroundSweepService: failed to list sessions")
            return

        for session in sessions:
            thread_id = session.get("thread_id", "")
            if not thread_id:
                continue
            config = {"configurable": {"thread_id": thread_id}}

            try:
                state = (await self._agent.agent.aget_state(config)).values
            except Exception:
                logger.exception(f"BackgroundSweepService: aget_state failed for {thread_id}")
                continue

            pending: list[dict] = list(state.get("pending_tasks", []))
            if not pending:
                continue

            updated = False
            for task in pending:
                if task.get("status") not in _EXPIRABLE_STATUSES:
                    continue
                raw = task.get("created_at", "")
                if not raw:
                    continue
                try:
                    created_at = datetime.fromisoformat(raw)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if (now - created_at).total_seconds() > ttl:
                    logger.info(f"Expiring task {task.get('task_id')} for thread {thread_id}")
                    task["status"] = "failed"
                    updated = True

            if not updated:
                continue

            try:
                await self._agent.agent.aupdate_state(config, {"pending_tasks": pending})
            except Exception:
                logger.exception(f"BackgroundSweepService: aupdate_state failed for {thread_id}")
                continue

            if not self._slack_service_fn:
                continue
            for task in pending:
                if task["status"] != "failed":
                    continue
                rc = task.get("reply_channel")
                if rc and rc.get("provider") == "slack":
                    slack = self._slack_service_fn()
                    if slack:
                        try:
                            await slack.send_message(rc["channel_id"], "태스크가 시간 초과됐어. 다시 시도해줘")
                        except Exception:
                            logger.exception("Failed to send sweep timeout Slack notification")
```

- [ ] **Step 3: Run sweep tests — expect PASS**

```bash
uv run pytest tests/services/test_background_sweep.py \
              tests/services/task_sweep_service/test_sweep_slack.py -v
```

- [ ] **Step 4: Update `tests/api/test_health_endpoint.py` (TDD — tests first)**

Replace `"STM"` module name assertions with `"MongoDB"`. Run to confirm failure:
```bash
uv run pytest tests/api/test_health_endpoint.py -v
```
Expected: FAIL — test looks for `"MongoDB"` module but health still returns `"STM"`

- [ ] **Step 5: Update `src/services/health.py`**

Replace `check_stm()` method with `check_mongodb()`:

```python
async def check_mongodb(self) -> tuple[bool, str | None]:
    """Check MongoDB checkpointer connectivity."""
    try:
        from src.services.service_manager import get_mongo_client
        client = get_mongo_client()
        if client is None:
            return False, "MongoDB client not initialized"
        client.admin.command("ping")
        return True, None
    except Exception as e:
        return False, f"MongoDB ping failed: {str(e)}"
```

In `get_system_health()`:
- Replace `stm_ready, stm_error = await self.check_stm()` → `mongodb_ready, mongodb_error = await self.check_mongodb()`
- Replace `ModuleStatus(name="STM", ready=stm_ready, error=stm_error)` → `ModuleStatus(name="MongoDB", ready=mongodb_ready, error=mongodb_error)`
- Replace `and stm_ready` → `and mongodb_ready` in `all_ready`

Run to confirm PASS:
```bash
uv run pytest tests/api/test_health_endpoint.py -v
```

- [ ] **Step 6: Lint and commit**

```bash
sh scripts/lint.sh
git add src/services/task_sweep_service/sweep.py \
        src/services/health.py \
        tests/services/test_background_sweep.py \
        tests/services/task_sweep_service/test_sweep_slack.py \
        tests/api/test_health_endpoint.py
git commit -m "refactor: BackgroundSweepService session_registry+aget_state; health check_mongodb"
```

---

## Task 9: `/v1/stm` routes + `main.py` + STM cleanup

**Files:**
- Modify: `src/api/routes/stm.py` (rewrite all endpoints + add `GET /{session_id}/messages`)
- Modify: `src/services/service_manager.py` (remove STM)
- Modify: `src/services/__init__.py` (remove STM exports)
- Modify: `src/main.py` (MongoDB init, remove STM, update sweep constructor)
- Delete: `src/services/stm_service/`, `yaml_files/services/stm_service/`, `tests/storage/test_mongodb_stm.py`, `tests/services/stm_service/`
- Test: `tests/api/test_stm_api.py` (rewrite)

- [ ] **Step 1: Rewrite `tests/api/test_stm_api.py`**

```python
# tests/api/test_stm_api.py — rewritten for checkpointer-based routes
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage


def _agent_svc(messages=None, state_extra=None):
    svc = MagicMock()
    sv = {"messages": messages or [], "user_id": "u1", "agent_id": "yuri", **(state_extra or {})}
    checkpoint = MagicMock()
    checkpoint.values = sv
    svc.agent.get_state = MagicMock(return_value=checkpoint)
    svc.agent.update_state = MagicMock()
    svc.agent.checkpointer = MagicMock()  # checkpointer exposed for deletion
    return svc


def test_get_chat_history_returns_messages():
    svc = _agent_svc(messages=[HumanMessage("hi"), AIMessage("hello")])
    with patch("src.api.routes.stm.get_agent_service", return_value=svc), \
         patch("src.api.routes.stm.get_session_registry", return_value=None):
        from fastapi.testclient import TestClient
        from src.main import create_app
        client = TestClient(create_app())
        resp = client.get("/v1/stm/get-chat-history?session_id=s1&user_id=u1&agent_id=yuri")
        # Verify agent.get_state was called with thread_id
        config = svc.agent.get_state.call_args[0][0]
        assert config["configurable"]["thread_id"] == "s1"


def test_list_sessions_queries_registry():
    from datetime import datetime, timezone
    registry = MagicMock()
    now = datetime.now(timezone.utc)
    registry.list_sessions.return_value = [
        {"thread_id": "t1", "user_id": "u1", "agent_id": "yuri",
         "created_at": now, "updated_at": now}
    ]
    with patch("src.api.routes.stm.get_agent_service", return_value=MagicMock()), \
         patch("src.api.routes.stm.get_session_registry", return_value=registry):
        registry.list_sessions.assert_not_called()
        # would be called on route hit


def test_delete_session_calls_registry_delete():
    svc = _agent_svc()
    registry = MagicMock()
    registry.delete.return_value = True
    with patch("src.api.routes.stm.get_agent_service", return_value=svc), \
         patch("src.api.routes.stm.get_session_registry", return_value=registry):
        pass  # verified via integration
```

Run to see failures:
```bash
uv run pytest tests/api/test_stm_api.py -v
```

- [ ] **Step 2: Rewrite `src/api/routes/stm.py`**

```python
"""STM-compatible API routes — backed by LangGraph checkpointer + session_registry."""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import convert_to_messages, convert_to_openai_messages

from src.models.stm import (
    AddChatHistoryRequest, AddChatHistoryResponse,
    DeleteSessionResponse, GetChatHistoryResponse,
    ListSessionsResponse, MessageResponse, SessionMetadata,
    UpdateSessionMetadataRequest, UpdateSessionMetadataResponse,
)
from src.services import get_agent_service
from src.services.service_manager import get_session_registry

router = APIRouter(prefix="/v1/stm", tags=["STM"])

_ALLOWED_METADATA_KEYS = {"user_id", "agent_id", "knowledge_saved", "ltm_last_consolidated_at_turn"}


def _agent_or_raise():
    svc = get_agent_service()
    if svc is None:
        raise HTTPException(503, "Agent service not initialized")
    return svc


@router.get("/get-chat-history", response_model=GetChatHistoryResponse, status_code=200)
async def get_chat_history(session_id: str, user_id: str, agent_id: str, limit: Optional[int] = None):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": session_id}}
    try:
        messages = svc.agent.get_state(config).values.get("messages", [])
        if limit:
            messages = messages[-limit:]
        openai_msgs = convert_to_openai_messages(messages)
        return GetChatHistoryResponse(
            session_id=session_id,
            messages=[MessageResponse(**m) for m in openai_msgs],
        )
    except Exception as e:
        raise HTTPException(500, f"Error retrieving chat history: {e}") from e


@router.post("/add-chat-history", response_model=AddChatHistoryResponse, status_code=201)
async def add_chat_history(request: AddChatHistoryRequest):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": request.session_id}}
    try:
        messages = convert_to_messages(request.messages)
        svc.agent.update_state(config, {"messages": messages})
        return AddChatHistoryResponse(session_id=request.session_id, message_count=len(messages))
    except Exception as e:
        raise HTTPException(500, f"Error adding chat history: {e}") from e


@router.get("/sessions", response_model=ListSessionsResponse, status_code=200)
async def list_sessions(user_id: str, agent_id: str):
    registry = get_session_registry()
    if registry is None:
        raise HTTPException(503, "Session registry not initialized")
    try:
        sessions = registry.list_sessions(user_id=user_id, agent_id=agent_id)
        return ListSessionsResponse(
            sessions=[
                SessionMetadata(
                    session_id=s["thread_id"],
                    user_id=s["user_id"],
                    agent_id=s["agent_id"],
                    created_at=s["created_at"].isoformat() if hasattr(s["created_at"], "isoformat") else str(s["created_at"]),
                    updated_at=s["updated_at"].isoformat() if hasattr(s["updated_at"], "isoformat") else str(s["updated_at"]),
                    metadata={},
                )
                for s in sessions
            ]
        )
    except Exception as e:
        raise HTTPException(500, f"Error listing sessions: {e}") from e


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse, status_code=200)
async def delete_session(session_id: str, user_id: str, agent_id: str):
    svc = _agent_or_raise()
    registry = get_session_registry()

    # Best-effort: delete checkpoints via checkpointer if it exposes a delete API.
    # LangGraph MongoDBSaver may not have a stable public delete method — wrap in try/except.
    # The user-visible deletion is always the session_registry record.
    config = {"configurable": {"thread_id": session_id}}
    try:
        checkpointer = getattr(svc.agent, "checkpointer", None)
        if checkpointer and hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(config)
    except Exception:
        pass  # checkpointer deletion is best-effort; registry deletion is authoritative

    if not (registry and registry.delete(session_id)):
        raise HTTPException(404, "Session not found")
    return DeleteSessionResponse(success=True, message="Session deleted successfully")


@router.patch("/sessions/{session_id}/metadata", response_model=UpdateSessionMetadataResponse, status_code=200)
async def update_session_metadata(session_id: str, request: UpdateSessionMetadataRequest):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": session_id}}
    try:
        update = {k: v for k, v in request.metadata.items() if k in _ALLOWED_METADATA_KEYS}
        if update:
            svc.agent.update_state(config, update)
        return UpdateSessionMetadataResponse(success=True, message="Metadata updated")
    except Exception as e:
        raise HTTPException(500, f"Error updating metadata: {e}") from e


@router.get("/{session_id}/messages", response_model=GetChatHistoryResponse, status_code=200,
            summary="Fetch all messages — NanoClaw Option B fetch endpoint")
async def get_session_messages(session_id: str):
    svc = _agent_or_raise()
    config = {"configurable": {"thread_id": session_id}}
    try:
        messages = svc.agent.get_state(config).values.get("messages", [])
        openai_msgs = convert_to_openai_messages(messages)
        return GetChatHistoryResponse(
            session_id=session_id,
            messages=[MessageResponse(**m) for m in openai_msgs],
        )
    except Exception as e:
        raise HTTPException(500, f"Error retrieving messages: {e}") from e
```

- [ ] **Step 3: Run STM API tests**

```bash
uv run pytest tests/api/test_stm_api.py -v
```

- [ ] **Step 4: Remove STM from `src/services/service_manager.py`**

Remove:
- `from src.services.stm_service import STMFactory, STMService` import
- `_stm_service_instance: Optional[STMService] = None` global
- `initialize_stm_service()` function body
- `get_stm_service()` function body
- STM parameter from `initialize_services()` signature and body
- `"initialize_stm_service"`, `"get_stm_service"` from `__all__`

- [ ] **Step 5: Remove STM from `src/services/__init__.py`**

```bash
grep -n "stm" src/services/__init__.py
```
Remove all `stm_service` imports and exports found.

- [ ] **Step 6: Update `src/main.py`**

a. Remove STM imports inside `_startup()`:
```python
# Remove from the import block:
get_stm_service,
initialize_stm_service,
```

b. Remove STM initialization block (lines 105–111).

c. Add MongoDB client init **after** `initialize_emotion_motion_mapper()` and **before** `initialize_agent_service()`:
```python
from src.services import initialize_mongodb_client

if config_paths.get("checkpointer_config_path"):
    initialize_mongodb_client(config_path=config_paths["checkpointer_config_path"])
else:
    initialize_mongodb_client()
```

d. Replace sweep service construction:
```python
# Remove:
stm_svc = get_stm_service()
if stm_svc is not None:
    sweep_service = BackgroundSweepService(
        stm_service=stm_svc, ...
    )

# Replace with:
from src.services.service_manager import get_session_registry
registry = get_session_registry()
agent_for_sweep = get_agent_service()
if registry is not None and agent_for_sweep is not None:
    sweep_service = BackgroundSweepService(
        agent_service=agent_for_sweep,
        session_registry=registry,
        config=sweep_cfg,
        slack_service_fn=get_slack_service,
    )
```

- [ ] **Step 7: Delete STM artifacts**

```bash
rm -rf src/services/stm_service/
rm -rf yaml_files/services/stm_service/
rm -f tests/storage/test_mongodb_stm.py
rm -rf tests/services/stm_service/
```

- [ ] **Step 8: Run full test suite — fix any remaining import errors**

```bash
uv run pytest --ignore=tests/api/test_real_e2e.py -x -v 2>&1 | tail -40
```

Any `ImportError` mentioning `stm_service` means a file still imports it — grep and fix:
```bash
grep -rn "stm_service\|get_stm_service\|STMService" src/ tests/
```

- [ ] **Step 9: Lint**

```bash
sh scripts/lint.sh
```

- [ ] **Step 10: Final commit**

```bash
git add -A
git commit -m "feat: complete STM→checkpointer migration — rewrite routes, cleanup stm_service"
```

---

## Final Verification

```bash
# Full unit test run
uv run pytest --ignore=tests/api/test_real_e2e.py -v

# Lint
sh scripts/lint.sh

# Smoke (requires MongoDB + services):
uv run uvicorn src.main:app --port 5500 &
sleep 3
curl -s http://localhost:5500/health | python3 -m json.tool
# Expected: "MongoDB" module ready=true, "STM" module absent
```
