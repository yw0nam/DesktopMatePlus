# Decouple STM/LTM from AgentService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove STM/LTM dependencies from AgentService so it only handles LLM inference; memory orchestration moves to a dedicated module consumed by the WebSocket layer.

**Architecture:** A new `memory_orchestrator.py` handles all STM/LTM I/O. `DelegateToolMiddleware` calls `get_stm_service()` at runtime. `handlers.py` passes memory context via `turn.metadata`. `event_handlers.py` intercepts `stream_end` to fire `save_turn()` before forwarding the clean event to the client.

**Tech Stack:** Python 3.13, asyncio, LangChain, pytest-asyncio, Loguru

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/services/websocket_service/manager/memory_orchestrator.py` | `load_context()` + `save_turn()` — all STM/LTM I/O |
| Create | `tests/services/test_memory_orchestrator.py` | Unit tests for the orchestrator |
| Modify | `src/services/agent_service/utils/delegate_middleware.py` | Remove constructor param; call `get_stm_service()` at runtime |
| Modify | `tests/agents/test_delegate_middleware.py` | Patch `get_stm_service` instead of passing stm_service |
| Modify | `src/services/agent_service/service.py` | Remove `save_memory()`, remove stm/ltm from abstract `stream()` |
| Modify | `src/services/agent_service/openai_chat_agent.py` | Remove `stm_service` from `__init__`; remove stm/ltm from `stream()`; add `new_chats` to `stream_end` yield |
| Modify | `src/services/service_manager.py` | Remove `stm_service` param from `initialize_agent_service` |
| Modify | `tests/agents/test_agent_service_manager.py` | Remove stm_service assertions |
| Modify | `src/services/websocket_service/manager/handlers.py` | Use `load_context()`; pass memory context via metadata |
| Modify | `src/services/websocket_service/message_processor/event_handlers.py` | Pop `new_chats` from `stream_end`; fire `save_turn()` |

---

## Task 1: Create `memory_orchestrator.py` with tests

**Files:**

- Create: `tests/services/test_memory_orchestrator.py`
- Create: `src/services/websocket_service/manager/memory_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/test_memory_orchestrator.py
import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.services.websocket_service.manager.memory_orchestrator import (
    load_context,
    save_turn,
)


@pytest.mark.asyncio
class TestLoadContext:
    async def test_returns_empty_list_when_no_services(self):
        result = await load_context(
            stm_service=None,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )
        assert result == []

    async def test_prepends_ltm_before_stm_history(self):
        stm = MagicMock()
        ltm = MagicMock()
        ltm.search_memory.return_value = {"results": [{"memory": "past event"}]}
        stm_msgs = [HumanMessage(content="hi")]
        stm.get_chat_history.return_value = stm_msgs

        result = await load_context(
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )

        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert "past event" in result[0].content
        assert result[1] is stm_msgs[0]
        # LTM searched only once
        ltm.search_memory.assert_called_once()

    async def test_skips_ltm_prefix_when_no_results(self):
        stm = MagicMock()
        ltm = MagicMock()
        ltm.search_memory.return_value = {"results": []}
        stm.get_chat_history.return_value = [HumanMessage(content="hi")]

        result = await load_context(
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

    async def test_returns_stm_history_without_ltm(self):
        stm = MagicMock()
        stm.get_chat_history.return_value = [HumanMessage(content="hi")]

        result = await load_context(
            stm_service=stm,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            query="hello",
            limit=10,
        )

        assert len(result) == 1


@pytest.mark.asyncio
class TestSaveTurn:
    async def test_saves_to_stm(self):
        stm = MagicMock()
        new_chats = [HumanMessage(content="hi")]

        await save_turn(
            new_chats=new_chats,
            stm_service=stm,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        stm.add_chat_history.assert_called_once_with(
            user_id="u1", agent_id="a1", session_id="s1", messages=new_chats
        )

    async def test_consolidates_to_ltm_at_interval(self):
        stm = MagicMock()
        ltm = MagicMock()
        new_chats = [HumanMessage(content="hi")]
        history = [HumanMessage(content=f"msg{i}") for i in range(10)]
        stm.get_chat_history.return_value = history
        stm.get_session_metadata.return_value = {"ltm_last_consolidated_at_turn": 0}

        await save_turn(
            new_chats=new_chats,
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        ltm.add_memory.assert_called_once()
        stm.update_session_metadata.assert_called()

    async def test_skips_ltm_consolidation_below_interval(self):
        stm = MagicMock()
        ltm = MagicMock()
        new_chats = [HumanMessage(content="hi")]
        history = [HumanMessage(content=f"msg{i}") for i in range(5)]
        stm.get_chat_history.return_value = history
        stm.get_session_metadata.return_value = {"ltm_last_consolidated_at_turn": 0}

        await save_turn(
            new_chats=new_chats,
            stm_service=stm,
            ltm_service=ltm,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        ltm.add_memory.assert_not_called()

    async def test_no_op_when_empty_new_chats(self):
        stm = MagicMock()

        await save_turn(
            new_chats=[],
            stm_service=stm,
            ltm_service=None,
            user_id="u1",
            agent_id="a1",
            session_id="s1",
        )

        stm.add_chat_history.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run pytest tests/services/test_memory_orchestrator.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Implement `memory_orchestrator.py`**

```python
# src/services/websocket_service/manager/memory_orchestrator.py
import asyncio
import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from src.services.ltm_service import LTMService
from src.services.stm_service import STMService

_LTM_CONSOLIDATION_INTERVAL = 10


async def load_context(
    stm_service: STMService | None,
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    session_id: str,
    query: str,
    limit: int = 10,
) -> list[BaseMessage]:
    """Load conversation context: optional LTM prefix + STM chat history.

    STM/LTM calls are synchronous; wrapped in asyncio.to_thread to avoid
    blocking the event loop.
    """
    ltm_prefix: list[BaseMessage] = []

    if ltm_service:
        search_result = await asyncio.to_thread(
            ltm_service.search_memory,
            query=query,
            user_id=user_id,
            agent_id=agent_id,
        )
        if search_result.get("results"):
            ltm_prefix = [
                SystemMessage(
                    content=f"Long-term memories: {json.dumps(search_result)}"
                )
            ]

    stm_history: list[BaseMessage] = []
    if stm_service:
        stm_history = await asyncio.to_thread(
            stm_service.get_chat_history,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            limit=limit,
        )

    return ltm_prefix + stm_history


async def save_turn(
    new_chats: list[BaseMessage],
    stm_service: STMService | None,
    ltm_service: LTMService | None,
    user_id: str,
    agent_id: str,
    session_id: str,
) -> None:
    """Persist new messages to STM; conditionally consolidate to LTM.

    Intended to run as a fire-and-forget background task via asyncio.create_task().
    STM/LTM calls are synchronous; wrapped in asyncio.to_thread.
    """
    try:
        if not new_chats or not stm_service:
            return

        await asyncio.to_thread(
            stm_service.add_chat_history,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            messages=new_chats,
        )
        logger.info(f"Chat history saved to STM: {session_id}")

        if not ltm_service:
            return

        metadata = await asyncio.to_thread(
            stm_service.get_session_metadata, session_id
        )
        last_consolidated = metadata.get("ltm_last_consolidated_at_turn", 0)

        history = await asyncio.to_thread(
            stm_service.get_chat_history,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        current_turn = sum(1 for m in history if isinstance(m, HumanMessage))

        if current_turn - last_consolidated < _LTM_CONSOLIDATION_INTERVAL:
            return

        slice_start = 0
        human_count = 0
        for idx, msg in enumerate(history):
            if isinstance(msg, HumanMessage):
                if human_count == last_consolidated:
                    slice_start = idx
                    break
                human_count += 1
        else:
            slice_start = len(history)

        ltm_result = await asyncio.to_thread(
            ltm_service.add_memory,
            messages=history[slice_start:],
            user_id=user_id,
            agent_id=agent_id,
        )
        await asyncio.to_thread(
            stm_service.update_session_metadata,
            session_id,
            {"ltm_last_consolidated_at_turn": current_turn},
        )
        logger.info(f"LTM consolidation at turn {current_turn}: {ltm_result}")

    except Exception as e:
        logger.error(f"Background memory save failed for session {session_id}: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/services/test_memory_orchestrator.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/websocket_service/manager/memory_orchestrator.py \
        tests/services/test_memory_orchestrator.py
git commit -m "feat: add memory_orchestrator for STM/LTM I/O"
```

---

## Task 2: Refactor `DelegateToolMiddleware` — runtime STM lookup

**Files:**

- Modify: `src/services/agent_service/utils/delegate_middleware.py`
- Modify: `tests/agents/test_delegate_middleware.py`

- [ ] **Step 1: Read current test file**

```bash
cat tests/agents/test_delegate_middleware.py
```

- [ ] **Step 2: Update tests to patch `get_stm_service` instead of injecting**

Any test that currently constructs `DelegateToolMiddleware(stm_service=mock_stm)` must change to:

```python
from unittest.mock import patch

with patch(
    "src.services.agent_service.utils.delegate_middleware.get_stm_service",
    return_value=mock_stm,
):
    middleware = DelegateToolMiddleware()
    ...
```

Tests that verify STM is `None` (middleware bypasses injection) should patch `get_stm_service` to return `None`.

- [ ] **Step 3: Run tests to confirm they now fail** (implementation not updated yet)

```bash
uv run pytest tests/agents/test_delegate_middleware.py -v
```

Expected: FAIL (constructor still requires `stm_service`)

- [ ] **Step 4: Rewrite `delegate_middleware.py`**

```python
"""DelegateToolMiddleware — injects DelegateTaskTool per request."""

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.config import get_config

from src.services.agent_service.tools.delegate import DelegateTaskTool
from src.services.service_manager import get_stm_service


class DelegateToolMiddleware(AgentMiddleware):
    """Middleware that injects DelegateTaskTool with per-request session_id.

    stm_service is fetched from the service registry at call time so this
    middleware carries no STM dependency at construction.
    """

    async def awrap_model_call(self, request, handler):
        stm_service = get_stm_service()
        if not stm_service:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=stm_service, session_id=session_id)
        return await handler(request.override(tools=[*request.tools, delegate]))

    async def awrap_tool_call(self, request, handler):
        _delegate_tool_name = DelegateTaskTool.model_fields["name"].default
        if request.tool_call["name"] != _delegate_tool_name:
            return await handler(request)
        stm_service = get_stm_service()
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=stm_service, session_id=session_id)
        return await handler(request.override(tool=delegate))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/agents/test_delegate_middleware.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/agent_service/utils/delegate_middleware.py \
        tests/agents/test_delegate_middleware.py
git commit -m "refactor: DelegateToolMiddleware resolves stm_service at runtime"
```

---

## Task 3: Remove STM/LTM from `AgentService` and `OpenAIChatAgent`

**Files:**

- Modify: `src/services/agent_service/service.py`
- Modify: `src/services/agent_service/openai_chat_agent.py`

**Note:** Task 2 must be complete before this task (middleware constructor changed).

- [ ] **Step 1: Rewrite `service.py`** — remove `save_memory()` and stm/ltm from abstract `stream()`

```python
# src/services/agent_service/service.py
from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


class AgentService(ABC):
    """Abstract base class for agent services."""

    def __init__(
        self,
        mcp_config: dict = None,
        support_image: bool = False,
    ):
        self.mcp_config = mcp_config
        self.support_image = support_image
        self.llm = self.initialize_model()

    @abstractmethod
    def initialize_model(self) -> BaseChatModel:
        """Initialize and return the language model."""

    async def initialize_async(self) -> None:
        """Async initialization: MCP tool fetch + agent creation. Default: no-op."""
        pass

    @abstractmethod
    async def is_healthy(self) -> tuple[bool, str]:
        """Check if the Agent is healthy and ready."""

    @abstractmethod
    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
    ):
        """Stream agent response.

        Yields dicts with type:
          stream_start | stream_token | tool_call | tool_result | stream_end | error

        stream_end payload includes ``new_chats: list[BaseMessage]`` — the new
        messages generated during this turn — so callers can persist them.
        """
```

- [ ] **Step 2: Update `openai_chat_agent.py`** — four targeted changes

  **2a. Remove `stm_service` from `__init__`** (lines 58-78):

  ```python
  def __init__(
      self,
      temperature: float,
      top_p: float,
      openai_api_key: str = None,
      openai_api_base: str = None,
      model_name: str = None,
      **kwargs,
  ):
      self.temperature = temperature
      self.top_p = top_p
      self.openai_api_key = openai_api_key
      self.openai_api_base = openai_api_base
      self.model_name = model_name
      self.agent = None
      self._mcp_tools: list = []
      self._personas: dict[str, str] = {}
      super().__init__(**kwargs)
      logger.info(f"Agent initialized: model={self.model_name}")
  ```

  **2b. Update `initialize_async`** — change middleware instantiation (line 112):

  ```python
  self.agent = create_agent(
      model=self.llm,
      tools=self._mcp_tools,
      middleware=[DelegateToolMiddleware()],   # no stm_service arg
  )
  ```

  **2c. Update `stream()` signature** — remove stm/ltm params:

  ```python
  async def stream(
      self,
      messages: list[BaseMessage],
      session_id: str = "",
      persona_id: str = "",
      user_id: str = "default_user",
      agent_id: str = "default_agent",
  ):
  ```

  **2d. Replace `save_memory` block with `new_chats` in `stream_end`**:

  Remove lines 166-177 (the `asyncio.create_task(self.save_memory(...))` block).

  Update the `stream_end` yield (currently lines 180-185) to include `new_chats`:

  ```python
  content = new_chats[-1].content if new_chats else ""
  yield {
      "type": "stream_end",
      "turn_id": turn_id,
      "session_id": session_id,
      "content": content,
      "new_chats": new_chats,   # ADD: callers pop this before forwarding to client
  }
  ```

  **2e. Remove unused imports**: `STMService`, `LTMService`, `Optional`

- [ ] **Step 3: Run agent tests**

```bash
uv run pytest tests/agents/ -v
```

Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/services/agent_service/service.py \
        src/services/agent_service/openai_chat_agent.py
git commit -m "refactor: AgentService is now a pure inference engine; stream_end carries new_chats"
```

---

## Task 4: Clean up `service_manager.py`

**Files:**

- Modify: `src/services/service_manager.py`
- Modify: `tests/agents/test_agent_service_manager.py`

- [ ] **Step 1: Remove `stm_service` from `initialize_agent_service`**

  Change signature and body (lines 179-221):

  ```python
  def initialize_agent_service(
      config_path: Optional[str | Path] = None,
      force_reinit: bool = False,
  ) -> AgentService:
      global _agent_service_instance

      if _agent_service_instance is not None and not force_reinit:
          logger.debug("Agent service already initialized, skipping")
          return _agent_service_instance

      _agent_service_instance = _initialize_service(
          service_name="Agent",
          default_config_path=_BASE_YAML
          / "services"
          / "agent_service"
          / "openai_chat_agent.yml",
          config_key="llm_config",
          factory_fn=AgentFactory.get_agent_service,
          config_path=config_path,
          async_health_check=True,
          swallow_health_error=True,
      )
      return _agent_service_instance
  ```

  Remove the `_inject_deps` inner function (lines 204-206) and the `pre_factory_hook=_inject_deps` kwarg.

- [ ] **Step 2: Update `initialize_services`** — remove stm-before-agent ordering comment and stm injection kwarg (lines 309-318):

  ```python
  tts_service = initialize_tts_service(
      config_path=tts_config_path, force_reinit=force_reinit
  )
  agent_service = initialize_agent_service(
      config_path=agent_config_path, force_reinit=force_reinit
  )
  stm_service = initialize_stm_service(
      config_path=stm_config_path, force_reinit=force_reinit
  )
  ```

- [ ] **Step 3: Update `test_agent_service_manager.py`**

  Find and update `test_initialize_services_with_custom_paths` (line ~395). Change:

  ```python
  # BEFORE
  mock_init_agent.assert_called_once_with(
      config_path=custom_agent_path,
      force_reinit=False,
      stm_service=mock_init_stm.return_value,
  )

  # AFTER
  mock_init_agent.assert_called_once_with(
      config_path=custom_agent_path,
      force_reinit=False,
  )
  ```

  Also remove any test that checks `stm_service` is passed through to the agent factory call_args.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/agents/test_agent_service_manager.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/service_manager.py \
        tests/agents/test_agent_service_manager.py
git commit -m "refactor: remove stm_service injection from initialize_agent_service"
```

---

## Task 5: Wire memory orchestrator into WebSocket layer

**Files:**

- Modify: `src/services/websocket_service/manager/handlers.py`
- Modify: `src/services/websocket_service/message_processor/event_handlers.py`

**Goal:** `handlers.py` uses `load_context()`; `event_handlers.py` intercepts `stream_end`, pops `new_chats` (keeping client event clean), and fires `save_turn()`.

### Part A — `handlers.py`

- [ ] **Step 1: Add import at top**

```python
from src.services.websocket_service.manager.memory_orchestrator import load_context
```

- [ ] **Step 2: Replace inline STM/LTM read block and update `agent_service.stream()` call**

  Find the block starting at line ~205. Replace from the LTM search block through the `agent_service.stream()` call:

  ```python
  # BEFORE (lines ~205-240)
  message_history = []
  if ltm_service:
      search_result = ltm_service.search_memory(...)
      ...
  if stm_service:
      message_history = stm_service.get_chat_history(...)

  content = [{"type": "text", "text": content}]
  if images and agent_service.support_image:
      content.extend(images)
  message_history.append(HumanMessage(content=content))

  agent_stream = agent_service.stream(
      messages=message_history,
      session_id=session_id,
      persona_id=persona_id,
      user_id=user_id,
      agent_id=agent_id,
      stm_service=stm_service,
      ltm_service=ltm_service,
  )
  ```

  ```python
  # AFTER
  # `content` is still the raw string here — pass it as query before reassigning
  message_history = await load_context(
      stm_service=stm_service,
      ltm_service=ltm_service,
      user_id=user_id,
      agent_id=agent_id,
      session_id=session_id,
      query=content,           # raw string, not yet reassigned to list
      limit=message_limit,
  )

  content = [{"type": "text", "text": content}]
  if images and agent_service.support_image:
      content.extend(images)
  message_history.append(HumanMessage(content=content))

  # Carry memory context into turn.metadata so event_handlers can fire save_turn
  metadata["agent_id"] = agent_id
  metadata["stm_service"] = stm_service
  metadata["ltm_service"] = ltm_service

  agent_stream = agent_service.stream(
      messages=message_history,
      session_id=session_id,
      persona_id=persona_id,
      user_id=user_id,
      agent_id=agent_id,
  )
  ```

- [ ] **Step 3: Remove the `stm_service is None` hard-exit guard** (lines ~150-156)

  `memory_orchestrator` degrades gracefully when `stm_service` is `None`. Remove or soften the guard so the conversation still proceeds without STM:

  ```python
  # REMOVE this block entirely:
  if stm_service is None:
      logger.error("STM service not initialized")
      await self.send_message(
          connection_id,
          ErrorMessage(error="STM service not initialized"),
      )
      return
  ```

### Part B — `event_handlers.py`

- [ ] **Step 4: Add imports at top of `event_handlers.py`**

```python
import asyncio

from src.services.websocket_service.manager.memory_orchestrator import save_turn
```

(`asyncio` is already imported — just add `save_turn`)

- [ ] **Step 5: Update `stream_end` handling** (lines 53-62)

  Pop `new_chats` from the event before forwarding to client, then fire `save_turn`:

  ```python
  if event_type == "stream_end":
      # Pop new_chats before forwarding — BaseMessage objects are not
      # JSON-serializable and must not reach the WebSocket client.
      new_chats = event.pop("new_chats", [])

      await self._signal_token_stream_closed(turn_id)
      await self._wait_for_token_queue(turn_id)
      await self.processor._wait_for_tts_tasks(turn_id)
      logger.info(
          f"Emitting stream_end for turn {turn_id} (all TTS chunks processed)"
      )
      await self.processor._put_event(turn_id, event)   # clean event, no new_chats
      await self.processor.complete_turn(turn_id)

      # Fire memory persistence in background using context stored in turn.metadata
      turn = self.processor.turns.get(turn_id)
      if new_chats and turn:
          meta = turn.metadata
          asyncio.create_task(
              save_turn(
                  new_chats=new_chats,
                  stm_service=meta.get("stm_service"),
                  ltm_service=meta.get("ltm_service"),
                  user_id=self.processor.user_id,
                  agent_id=meta.get("agent_id", ""),
                  session_id=turn.session_id,
              ),
              name=f"save-memory-{turn_id}",
          )
      continue
  ```

- [ ] **Step 6: Run the full test suite**

```bash
uv run pytest -v
```

Expected: All PASS

- [ ] **Step 7: Lint**

```bash
sh scripts/lint.sh
```

Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add src/services/websocket_service/manager/handlers.py \
        src/services/websocket_service/message_processor/event_handlers.py
git commit -m "refactor: wire memory_orchestrator into WebSocket layer; event_handlers saves turn memory"
```

---

## Final Verification

- [ ] **Run full test suite**: `uv run pytest -v`

- [ ] **Confirm agent_service has no STM/LTM imports**:

```bash
grep -r "STMService\|LTMService\|stm_service\|ltm_service" \
    src/services/agent_service/ \
    --include="*.py" \
    | grep -v "tools/delegate"
```

Expected: No output (only `tools/delegate/` is allowed to reference STM)
