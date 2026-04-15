# Proactive Talking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add proactive talking — the AI character initiates conversation via idle detection (Phase 1), scheduled triggers (Phase 2), and webhook API (Phase 3).

**Architecture:** Single `ProactiveService` following the `BackgroundSweepService` pattern. Three trigger sources share a common `trigger_proactive()` execution flow (lock → idle recheck → cooldown → agent stream → TTS + WS push). YAML-based prompt templates and per-persona timeout overrides.

**Tech Stack:** Python 3.13, FastAPI, APScheduler, asyncio, Pydantic V2, LangChain/LangGraph, pytest

**Design Spec:** `docs/plans/2026-04-15-proactive-talking-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/services/proactive_service/__init__.py` | Re-exports `ProactiveService` |
| `src/services/proactive_service/config.py` | `ProactiveConfig` Pydantic model |
| `src/services/proactive_service/prompt_loader.py` | YAML template loading + `str.format()` rendering |
| `src/services/proactive_service/idle_watcher.py` | Periodic idle scan loop |
| `src/services/proactive_service/schedule_manager.py` | APScheduler wrapper |
| `src/services/proactive_service/proactive_service.py` | Orchestrator: `start()`, `stop()`, `trigger_proactive()` |
| `src/api/routes/proactive.py` | `POST /v1/proactive/trigger` endpoint |
| `src/models/proactive.py` | Request/response Pydantic models for webhook |
| `yaml_files/proactive_prompts.yml` | Trigger-type prompt templates |
| `tests/services/proactive_service/__init__.py` | Test package init |
| `tests/services/proactive_service/test_config.py` | Config model tests |
| `tests/services/proactive_service/test_prompt_loader.py` | Prompt loader tests |
| `tests/services/proactive_service/test_idle_watcher.py` | Idle watcher logic tests |
| `tests/services/proactive_service/test_schedule_manager.py` | Schedule manager tests |
| `tests/services/proactive_service/test_proactive_service.py` | Orchestrator tests |
| `tests/api/test_proactive_route.py` | Webhook endpoint tests |
| `tests/e2e/test_proactive_e2e.py` | E2E proactive tests |

### Modified Files

| File | Change |
|------|--------|
| `src/services/websocket_service/manager/connection.py` | Add `last_user_message_at` field |
| `src/services/websocket_service/manager/handlers.py` | Update timestamp on chat message |
| `src/models/websocket.py` | Add `proactive: bool \| None = None` to `StreamStartMessage` |
| ~~`src/services/websocket_service/message_processor/event_handlers.py`~~ | Not modified — proactive uses direct WS send, not the MessageProcessor pipeline |
| `src/services/service_manager.py` | Add `initialize_proactive_service()` + getter |
| `src/main.py` | Register proactive service in lifespan |
| `src/api/routes/__init__.py` | Include proactive router |
| `yaml_files/services.yml` | Add `proactive` config section |
| `yaml_files/services.e2e.yml` | Add `proactive` section with short timeouts |
| `yaml_files/personas.yml` | Add `idle_timeout_seconds` override for yuri |
| `pyproject.toml` | Add `apscheduler` dependency |

---

## Task 1: Add APScheduler dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add apscheduler to dependencies**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv add apscheduler
```

- [ ] **Step 2: Verify installation**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run python -c "from apscheduler.schedulers.asyncio import AsyncIOScheduler; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add apscheduler dependency for proactive talking"
```

---

## Task 2: ProactiveConfig model + YAML prompt templates

**Files:**
- Create: `src/services/proactive_service/__init__.py`
- Create: `src/services/proactive_service/config.py`
- Create: `yaml_files/proactive_prompts.yml`
- Modify: `yaml_files/services.yml`
- Modify: `yaml_files/personas.yml`
- Test: `tests/services/proactive_service/__init__.py`
- Test: `tests/services/proactive_service/test_config.py`

- [ ] **Step 1: Write failing tests for ProactiveConfig**

Create `tests/services/proactive_service/__init__.py` (empty file).

Create `tests/services/proactive_service/test_config.py`:

```python
"""Tests for ProactiveConfig Pydantic model."""

import pytest

from src.services.proactive_service.config import ProactiveConfig, ScheduleEntry


class TestProactiveConfig:
    def test_defaults_are_reasonable(self):
        cfg = ProactiveConfig()
        assert cfg.idle_timeout_seconds == 300
        assert cfg.cooldown_seconds == 600
        assert cfg.watcher_interval_seconds == 30
        assert cfg.schedules == []

    def test_custom_values(self):
        cfg = ProactiveConfig(
            idle_timeout_seconds=180,
            cooldown_seconds=120,
            watcher_interval_seconds=10,
        )
        assert cfg.idle_timeout_seconds == 180
        assert cfg.cooldown_seconds == 120
        assert cfg.watcher_interval_seconds == 10

    def test_minimum_values_enforced(self):
        with pytest.raises(Exception):
            ProactiveConfig(idle_timeout_seconds=0)
        with pytest.raises(Exception):
            ProactiveConfig(cooldown_seconds=-1)
        with pytest.raises(Exception):
            ProactiveConfig(watcher_interval_seconds=0)


class TestScheduleEntry:
    def test_valid_schedule(self):
        entry = ScheduleEntry(
            id="morning",
            cron="0 9 * * *",
            prompt_key="morning",
            enabled=True,
        )
        assert entry.id == "morning"
        assert entry.enabled is True

    def test_disabled_by_default(self):
        entry = ScheduleEntry(id="x", cron="* * * * *", prompt_key="x")
        assert entry.enabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.services.proactive_service'`

- [ ] **Step 3: Create ProactiveConfig**

Create `src/services/proactive_service/__init__.py`:

```python
"""Proactive talking service — AI-initiated conversation triggers."""
```

Create `src/services/proactive_service/config.py`:

```python
"""Configuration models for proactive talking service."""

from pydantic import BaseModel, Field


class ScheduleEntry(BaseModel):
    """A single scheduled proactive trigger."""

    id: str = Field(..., description="Unique schedule identifier")
    cron: str = Field(..., description="Cron expression (e.g. '0 9 * * *')")
    prompt_key: str = Field(..., description="Key in proactive_prompts.yml")
    enabled: bool = Field(default=True, description="Whether this schedule is active")


class ProactiveConfig(BaseModel):
    """Configuration for the proactive talking service."""

    idle_timeout_seconds: int = Field(default=300, ge=1)
    cooldown_seconds: int = Field(default=600, ge=0)
    watcher_interval_seconds: int = Field(default=30, ge=1)
    schedules: list[ScheduleEntry] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_config.py -v
```

Expected: All PASS

- [ ] **Step 5: Create YAML prompt template file**

Create `yaml_files/proactive_prompts.yml`:

```yaml
# Proactive talking prompt templates.
# Variables: {idle_seconds}, {current_time}, {context}
# Rendered via str.format() before passing to agent.

idle: |
  유저가 {idle_seconds}초 동안 조용합니다.
  현재 시각은 {current_time}입니다.
  자연스럽게 말을 걸어주세요.

morning: |
  현재 시각은 {current_time}입니다.
  아침 인사를 해주세요.

webhook: |
  외부 트리거가 발생했습니다.
  컨텍스트: {context}
  이 상황에 맞게 유저에게 알려주세요.
```

- [ ] **Step 6: Add proactive section to services.yml**

Append to `yaml_files/services.yml` after the `summary_config` section:

```yaml
# -----------------------------------------------------------------------------
# Proactive Talking Service
# -----------------------------------------------------------------------------
proactive:
  idle_timeout_seconds: 300
  cooldown_seconds: 600
  watcher_interval_seconds: 30
  schedules:
    - id: morning_greeting
      cron: "0 9 * * *"
      prompt_key: morning
      enabled: true
```

- [ ] **Step 7: Add idle_timeout_seconds override to personas.yml**

Add `idle_timeout_seconds: 180` to the yuri persona in `yaml_files/personas.yml`:

```yaml
personas:
  yuri:
    idle_timeout_seconds: 180
    system_prompt: |
      ...existing content...
```

- [ ] **Step 8: Commit**

```bash
git add src/services/proactive_service/ tests/services/proactive_service/ yaml_files/proactive_prompts.yml yaml_files/services.yml yaml_files/personas.yml
git commit -m "feat: add ProactiveConfig model and YAML prompt templates"
```

---

## Task 3: PromptLoader

**Files:**
- Create: `src/services/proactive_service/prompt_loader.py`
- Test: `tests/services/proactive_service/test_prompt_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/services/proactive_service/test_prompt_loader.py`:

```python
"""Tests for proactive prompt template loader."""

import pytest

from src.services.proactive_service.prompt_loader import PromptLoader


@pytest.fixture
def loader(tmp_path):
    prompts_file = tmp_path / "proactive_prompts.yml"
    prompts_file.write_text(
        "idle: |\n"
        "  유저가 {idle_seconds}초 동안 조용합니다.\n"
        "  현재 시각은 {current_time}입니다.\n"
        "webhook: |\n"
        "  컨텍스트: {context}\n"
    )
    return PromptLoader(prompts_file)


class TestPromptLoader:
    def test_render_idle_prompt(self, loader):
        result = loader.render("idle", idle_seconds=300, current_time="09:00:00")
        assert "300초" in result
        assert "09:00:00" in result

    def test_render_webhook_prompt(self, loader):
        result = loader.render("webhook", context="서버 점검")
        assert "서버 점검" in result

    def test_missing_key_returns_fallback(self, loader):
        result = loader.render("nonexistent", context="test")
        assert "nonexistent" in result  # fallback includes trigger type

    def test_missing_variable_left_as_placeholder(self, loader):
        # Missing variables should not raise, just leave placeholder
        result = loader.render("idle", idle_seconds=300)
        assert "300" in result
        assert "{current_time}" in result

    def test_reload(self, loader, tmp_path):
        prompts_file = tmp_path / "proactive_prompts.yml"
        prompts_file.write_text("idle: |\n  새 프롬프트 {idle_seconds}\n")
        loader.reload()
        result = loader.render("idle", idle_seconds=100)
        assert "새 프롬프트" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_prompt_loader.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement PromptLoader**

Create `src/services/proactive_service/prompt_loader.py`:

```python
"""YAML-based prompt template loader for proactive triggers."""

from pathlib import Path

import yaml
from loguru import logger

_DEFAULT_PROMPTS_PATH = (
    Path(__file__).resolve().parents[3] / "yaml_files" / "proactive_prompts.yml"
)


class PromptLoader:
    """Loads and renders proactive prompt templates from YAML."""

    def __init__(self, prompts_path: Path | None = None):
        self._path = prompts_path or _DEFAULT_PROMPTS_PATH
        self._templates: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)load prompt templates from YAML file."""
        if not self._path.exists():
            logger.warning(f"Proactive prompts file not found: {self._path}")
            self._templates = {}
            return
        with open(self._path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._templates = {k: str(v) for k, v in data.items()}
        logger.info(f"Loaded {len(self._templates)} proactive prompt templates")

    def render(self, trigger_type: str, **kwargs: object) -> str:
        """Render a prompt template with the given variables.

        Missing template keys produce a fallback prompt.
        Missing variables are left as `{placeholder}` in the output.
        """
        template = self._templates.get(trigger_type)
        if template is None:
            logger.warning(f"No prompt template for trigger type: {trigger_type}")
            return f"Proactive trigger: {trigger_type}"
        # Use format_map so missing keys don't raise KeyError
        return template.format_map(_SafeDict(kwargs))


class _SafeDict(dict):
    """Dict subclass that returns '{key}' for missing keys."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_prompt_loader.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/proactive_service/prompt_loader.py tests/services/proactive_service/test_prompt_loader.py
git commit -m "feat: add PromptLoader for proactive prompt templates"
```

---

## Task 4: ConnectionState timestamp + handlers update

**Files:**
- Modify: `src/services/websocket_service/manager/connection.py:11-29`
- Modify: `src/services/websocket_service/manager/handlers.py:111-246`
- Test: `tests/services/proactive_service/test_idle_watcher.py` (connection state portion)

- [ ] **Step 1: Write failing test for ConnectionState**

Add to `tests/services/proactive_service/test_idle_watcher.py`:

```python
"""Tests for idle watcher and ConnectionState timestamp."""

import time
from unittest.mock import MagicMock
from uuid import uuid4

from src.services.websocket_service.manager.connection import ConnectionState


class TestConnectionStateTimestamp:
    def test_last_user_message_at_initialized_to_created_at(self):
        ws = MagicMock()
        conn = ConnectionState(ws, uuid4())
        assert conn.last_user_message_at == conn.created_at

    def test_last_user_message_at_is_updatable(self):
        ws = MagicMock()
        conn = ConnectionState(ws, uuid4())
        now = time.time()
        conn.last_user_message_at = now
        assert conn.last_user_message_at == now
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_idle_watcher.py::TestConnectionStateTimestamp -v
```

Expected: `AttributeError: 'ConnectionState' object has no attribute 'last_user_message_at'`

- [ ] **Step 3: Add `last_user_message_at` to ConnectionState**

In `src/services/websocket_service/manager/connection.py`, add after `self.created_at = time.time()`:

```python
        self.last_user_message_at: float = self.created_at
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_idle_watcher.py::TestConnectionStateTimestamp -v
```

Expected: All PASS

- [ ] **Step 5: Update handlers.py to set timestamp on chat message**

In `src/services/websocket_service/manager/handlers.py`, in `handle_chat_message()`, add right after the authentication check passes (after line 140, before `agent_service = get_agent_service()`):

```python
        # Update idle tracking timestamp
        import time as _time
        connection_state.last_user_message_at = _time.time()
```

- [ ] **Step 6: Commit**

```bash
git add src/services/websocket_service/manager/connection.py src/services/websocket_service/manager/handlers.py tests/services/proactive_service/test_idle_watcher.py
git commit -m "feat: add last_user_message_at timestamp to ConnectionState"
```

---

## Task 5: IdleWatcher

**Files:**
- Create: `src/services/proactive_service/idle_watcher.py`
- Test: `tests/services/proactive_service/test_idle_watcher.py` (extend)

- [ ] **Step 1: Write failing tests for IdleWatcher**

Append to `tests/services/proactive_service/test_idle_watcher.py`:

```python
import asyncio
from unittest.mock import AsyncMock

import pytest

from src.services.proactive_service.config import ProactiveConfig
from src.services.proactive_service.idle_watcher import IdleWatcher


def _make_connection(idle_seconds: float = 400.0):
    """Create a mock ConnectionState that has been idle for `idle_seconds`."""
    conn = MagicMock()
    conn.is_authenticated = True
    conn.is_closing = False
    conn.last_user_message_at = time.time() - idle_seconds
    conn.connection_id = uuid4()
    conn.user_id = "test_user"
    conn.message_processor = MagicMock()
    conn.message_processor._current_turn_id = None
    return conn


class TestIdleWatcher:
    async def test_detects_idle_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_called_once()

    async def test_skips_active_connection(self):
        conn = _make_connection(idle_seconds=10.0)  # recently active
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_skips_unauthenticated_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        conn.is_authenticated = False
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_skips_closing_connection(self):
        conn = _make_connection(idle_seconds=400.0)
        conn.is_closing = True
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_skips_connection_with_active_turn(self):
        conn = _make_connection(idle_seconds=400.0)
        conn.message_processor._current_turn_id = "active-turn"
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
        )
        await watcher.scan_once()
        trigger_fn.assert_not_called()

    async def test_uses_persona_override_timeout(self):
        conn = _make_connection(idle_seconds=200.0)  # idle 200s
        trigger_fn = AsyncMock()
        config = ProactiveConfig(idle_timeout_seconds=300, watcher_interval_seconds=1)
        # persona override: 150s → should trigger
        watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: {conn.connection_id: conn},
            trigger_fn=trigger_fn,
            persona_overrides={"yuri": 150},
        )
        # Simulate that this connection uses persona "yuri"
        conn.message_processor.turns = {}
        await watcher.scan_once(get_persona_fn=lambda cid: "yuri")
        trigger_fn.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_idle_watcher.py::TestIdleWatcher -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement IdleWatcher**

Create `src/services/proactive_service/idle_watcher.py`:

```python
"""Idle connection watcher — triggers proactive talk after inactivity."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from src.services.proactive_service.config import ProactiveConfig

if TYPE_CHECKING:
    from src.services.websocket_service.manager.connection import ConnectionState


class IdleWatcher:
    """Periodically scans connections for idle users."""

    def __init__(
        self,
        config: ProactiveConfig,
        get_connections_fn: Callable[[], dict[UUID, ConnectionState]],
        trigger_fn: Callable[..., Any],
        persona_overrides: dict[str, int] | None = None,
    ):
        self._config = config
        self._get_connections = get_connections_fn
        self._trigger = trigger_fn
        self._persona_overrides = persona_overrides or {}
        self._task: asyncio.Task | None = None
        # Track which connections already had a proactive trigger fired
        # to enforce "1 trigger per idle period" rule.
        self._triggered_connections: set[UUID] = set()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="idle_watcher_loop")
        logger.info(
            f"IdleWatcher started (interval={self._config.watcher_interval_seconds}s, "
            f"timeout={self._config.idle_timeout_seconds}s)"
        )

    async def stop(self) -> None:
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        logger.info("IdleWatcher stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("IdleWatcher: unhandled error during scan")
            await asyncio.sleep(self._config.watcher_interval_seconds)

    async def scan_once(
        self,
        get_persona_fn: Callable[[UUID], str] | None = None,
    ) -> None:
        """Scan all connections and trigger proactive talk for idle ones."""
        now = time.time()
        connections = self._get_connections()

        for connection_id, conn in connections.items():
            if not conn.is_authenticated or conn.is_closing:
                continue

            # Skip if a turn is already active
            mp = conn.message_processor
            if not mp or mp._current_turn_id is not None:
                continue

            # Determine timeout (persona override or default)
            timeout = self._config.idle_timeout_seconds
            if get_persona_fn is not None:
                persona = get_persona_fn(connection_id)
                if persona in self._persona_overrides:
                    timeout = self._persona_overrides[persona]

            idle_seconds = now - conn.last_user_message_at
            if idle_seconds < timeout:
                # Connection became active again — reset trigger tracking
                self._triggered_connections.discard(connection_id)
                continue

            # Already triggered for this idle period
            if connection_id in self._triggered_connections:
                continue

            self._triggered_connections.add(connection_id)
            logger.info(
                f"Idle detected: connection {connection_id} idle for {idle_seconds:.0f}s "
                f"(threshold {timeout}s)"
            )
            await self._trigger(
                connection_id=connection_id,
                trigger_type="idle",
                idle_seconds=int(idle_seconds),
            )

    def reset_connection(self, connection_id: UUID) -> None:
        """Reset trigger tracking when a connection sends a message."""
        self._triggered_connections.discard(connection_id)
```

- [ ] **Step 4: Run tests**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_idle_watcher.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/proactive_service/idle_watcher.py tests/services/proactive_service/test_idle_watcher.py
git commit -m "feat: add IdleWatcher for proactive idle detection"
```

---

## Task 6: ScheduleManager

**Files:**
- Create: `src/services/proactive_service/schedule_manager.py`
- Test: `tests/services/proactive_service/test_schedule_manager.py`

- [ ] **Step 1: Write failing tests**

Create `tests/services/proactive_service/test_schedule_manager.py`:

```python
"""Tests for ScheduleManager (APScheduler wrapper)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.proactive_service.config import ProactiveConfig, ScheduleEntry
from src.services.proactive_service.schedule_manager import ScheduleManager


def _make_config(schedules=None):
    return ProactiveConfig(
        schedules=schedules or [],
        watcher_interval_seconds=30,
    )


class TestScheduleManager:
    async def test_start_registers_jobs(self):
        config = _make_config(
            schedules=[
                ScheduleEntry(id="morning", cron="0 9 * * *", prompt_key="morning"),
            ]
        )
        trigger_fn = AsyncMock()
        get_connections_fn = MagicMock(return_value={})
        mgr = ScheduleManager(
            config=config,
            trigger_fn=trigger_fn,
            get_connections_fn=get_connections_fn,
        )
        await mgr.start()
        assert mgr.is_running()
        await mgr.stop()

    async def test_disabled_schedule_is_skipped(self):
        config = _make_config(
            schedules=[
                ScheduleEntry(
                    id="disabled", cron="0 9 * * *", prompt_key="x", enabled=False
                ),
            ]
        )
        trigger_fn = AsyncMock()
        get_connections_fn = MagicMock(return_value={})
        mgr = ScheduleManager(
            config=config,
            trigger_fn=trigger_fn,
            get_connections_fn=get_connections_fn,
        )
        await mgr.start()
        # No jobs should be registered for disabled schedules
        jobs = mgr._scheduler.get_jobs()
        assert len(jobs) == 0
        await mgr.stop()

    async def test_trigger_broadcasts_to_connections(self):
        conn = MagicMock()
        conn.connection_id = uuid4()
        conn.is_authenticated = True
        conn.is_closing = False
        trigger_fn = AsyncMock()
        config = _make_config()
        get_connections_fn = MagicMock(
            return_value={conn.connection_id: conn}
        )
        mgr = ScheduleManager(
            config=config,
            trigger_fn=trigger_fn,
            get_connections_fn=get_connections_fn,
        )
        await mgr._on_schedule_fire(
            schedule_id="morning", prompt_key="morning"
        )
        trigger_fn.assert_called_once_with(
            connection_id=conn.connection_id,
            trigger_type="scheduled",
            prompt_key="morning",
        )

    async def test_no_connections_is_noop(self):
        trigger_fn = AsyncMock()
        config = _make_config()
        get_connections_fn = MagicMock(return_value={})
        mgr = ScheduleManager(
            config=config,
            trigger_fn=trigger_fn,
            get_connections_fn=get_connections_fn,
        )
        await mgr._on_schedule_fire(
            schedule_id="morning", prompt_key="morning"
        )
        trigger_fn.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_schedule_manager.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement ScheduleManager**

Create `src/services/proactive_service/schedule_manager.py`:

```python
"""APScheduler-based schedule manager for time-triggered proactive talks."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.services.proactive_service.config import ProactiveConfig

if TYPE_CHECKING:
    from src.services.websocket_service.manager.connection import ConnectionState


class ScheduleManager:
    """Manages APScheduler jobs for scheduled proactive triggers."""

    def __init__(
        self,
        config: ProactiveConfig,
        trigger_fn: Callable[..., Any],
        get_connections_fn: Callable[[], dict[UUID, ConnectionState]],
    ):
        self._config = config
        self._trigger = trigger_fn
        self._get_connections = get_connections_fn
        self._scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        """Register scheduled jobs and start the scheduler."""
        for entry in self._config.schedules:
            if not entry.enabled:
                logger.info(f"Schedule '{entry.id}' is disabled, skipping")
                continue

            try:
                trigger = CronTrigger.from_crontab(entry.cron)
                self._scheduler.add_job(
                    self._on_schedule_fire,
                    trigger=trigger,
                    id=f"proactive_{entry.id}",
                    kwargs={
                        "schedule_id": entry.id,
                        "prompt_key": entry.prompt_key,
                    },
                    replace_existing=True,
                )
                logger.info(
                    f"Registered proactive schedule '{entry.id}' "
                    f"(cron={entry.cron}, prompt={entry.prompt_key})"
                )
            except Exception:
                logger.exception(f"Failed to register schedule '{entry.id}'")

        self._scheduler.start()
        logger.info("ScheduleManager started")

    async def stop(self) -> None:
        """Shutdown the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("ScheduleManager stopped")

    def is_running(self) -> bool:
        return self._scheduler.running

    async def _on_schedule_fire(
        self, schedule_id: str, prompt_key: str
    ) -> None:
        """Called by APScheduler when a cron job fires."""
        connections = self._get_connections()
        active = {
            cid: conn
            for cid, conn in connections.items()
            if conn.is_authenticated and not conn.is_closing
        }

        if not active:
            logger.info(
                f"Schedule '{schedule_id}' fired but no active connections, skipping"
            )
            return

        logger.info(
            f"Schedule '{schedule_id}' fired, triggering {len(active)} connection(s)"
        )
        for connection_id, conn in active.items():
            await self._trigger(
                connection_id=connection_id,
                trigger_type="scheduled",
                prompt_key=prompt_key,
            )
```

- [ ] **Step 4: Run tests**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_schedule_manager.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/proactive_service/schedule_manager.py tests/services/proactive_service/test_schedule_manager.py
git commit -m "feat: add ScheduleManager for time-based proactive triggers"
```

---

## Task 7: StreamStartMessage `proactive` field + event tagging

**Files:**
- Modify: `src/models/websocket.py:177-183`
- Modify: `src/services/websocket_service/message_processor/event_handlers.py:298-308`

- [ ] **Step 1: Add `proactive` field to StreamStartMessage**

In `src/models/websocket.py`, modify `StreamStartMessage`:

```python
class StreamStartMessage(BaseMessage):
    """Server message indicating the start of a stream."""

    type: MessageType = MessageType.STREAM_START
    turn_id: str
    session_id: str
    proactive: bool | None = None
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/ -m "not slow and not e2e" -x -q
```

Expected: All PASS (new optional field shouldn't break anything)

- [ ] **Step 3: Commit**

```bash
git add src/models/websocket.py
git commit -m "feat: add proactive flag to StreamStartMessage"
```

---

## Task 8: ProactiveService orchestrator

**Files:**
- Create: `src/services/proactive_service/proactive_service.py`
- Test: `tests/services/proactive_service/test_proactive_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/services/proactive_service/test_proactive_service.py`:

```python
"""Tests for ProactiveService — the main orchestrator."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.proactive_service.config import ProactiveConfig
from src.services.proactive_service.proactive_service import ProactiveService


def _make_connection(idle_seconds: float = 400.0):
    conn = MagicMock()
    conn.connection_id = uuid4()
    conn.is_authenticated = True
    conn.is_closing = False
    conn.last_user_message_at = time.time() - idle_seconds
    conn.user_id = "test_user"
    conn.message_processor = MagicMock()
    conn.message_processor._current_turn_id = None
    conn.websocket = MagicMock()
    return conn


@pytest.fixture
def proactive_service(tmp_path):
    prompts_file = tmp_path / "proactive_prompts.yml"
    prompts_file.write_text(
        "idle: |\n  유저가 {idle_seconds}초 동안 조용합니다.\n"
        "webhook: |\n  컨텍스트: {context}\n"
    )
    config = ProactiveConfig(
        idle_timeout_seconds=300,
        cooldown_seconds=10,
        watcher_interval_seconds=60,
    )
    ws_manager = MagicMock()
    ws_manager.connections = {}
    agent_service = AsyncMock()

    async def mock_stream(**kwargs):
        yield {"type": "stream_start", "turn_id": "t1", "session_id": "s1"}
        yield {"type": "stream_token", "chunk": "Hello!"}
        yield {
            "type": "stream_end",
            "turn_id": "t1",
            "session_id": "s1",
            "content": "Hello!",
            "new_chats": [],
        }

    agent_service.stream = mock_stream

    svc = ProactiveService(
        config=config,
        ws_manager=ws_manager,
        agent_service=agent_service,
        prompts_path=prompts_file,
    )
    return svc


class TestTriggerProactive:
    async def test_trigger_succeeds(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {
            conn.connection_id: conn
        }
        proactive_service._ws_manager._get_connection = MagicMock(
            return_value=conn
        )

        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result["status"] == "triggered"

    async def test_trigger_skipped_when_connection_not_found(self, proactive_service):
        result = await proactive_service.trigger_proactive(
            connection_id=uuid4(),
            trigger_type="idle",
        )
        assert result["status"] == "skipped"
        assert "not found" in result["reason"]

    async def test_cooldown_blocks_repeated_trigger(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        proactive_service._ws_manager.connections = {
            conn.connection_id: conn
        }
        proactive_service._ws_manager._get_connection = MagicMock(
            return_value=conn
        )

        # First trigger should succeed
        result1 = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result1["status"] == "triggered"

        # Second trigger should be blocked by cooldown
        result2 = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
            idle_seconds=400,
        )
        assert result2["status"] == "skipped"
        assert "cooldown" in result2["reason"]

    async def test_trigger_skipped_when_active_turn(self, proactive_service):
        conn = _make_connection(idle_seconds=400.0)
        conn.message_processor._current_turn_id = "active-turn"
        proactive_service._ws_manager.connections = {
            conn.connection_id: conn
        }
        proactive_service._ws_manager._get_connection = MagicMock(
            return_value=conn
        )

        result = await proactive_service.trigger_proactive(
            connection_id=conn.connection_id,
            trigger_type="idle",
        )
        assert result["status"] == "skipped"
        assert "active turn" in result["reason"]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_proactive_service.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement ProactiveService**

Create `src/services/proactive_service/proactive_service.py`:

```python
"""ProactiveService — orchestrates all proactive talking triggers."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from src.services.proactive_service.config import ProactiveConfig
from src.services.proactive_service.idle_watcher import IdleWatcher
from src.services.proactive_service.prompt_loader import PromptLoader
from src.services.proactive_service.schedule_manager import ScheduleManager

if TYPE_CHECKING:
    from src.services.agent_service.service import AgentService
    from src.services.websocket_service.manager.websocket_manager import (
        WebSocketManager,
    )


class ProactiveService:
    """Orchestrates proactive talking: idle watch, schedules, webhook triggers."""

    def __init__(
        self,
        config: ProactiveConfig,
        ws_manager: WebSocketManager,
        agent_service: AgentService,
        prompts_path: Path | None = None,
        persona_overrides: dict[str, int] | None = None,
    ):
        self._config = config
        self._ws_manager = ws_manager
        self._agent_service = agent_service
        self._prompt_loader = PromptLoader(prompts_path)
        self._persona_overrides = persona_overrides or {}

        # Per-connection cooldown tracking: connection_id → last trigger timestamp
        self._last_proactive_at: dict[UUID, float] = {}

        self._idle_watcher = IdleWatcher(
            config=config,
            get_connections_fn=lambda: self._ws_manager.connections,
            trigger_fn=self.trigger_proactive,
            persona_overrides=self._persona_overrides,
        )
        self._schedule_manager = ScheduleManager(
            config=config,
            trigger_fn=self.trigger_proactive,
            get_connections_fn=lambda: self._ws_manager.connections,
        )

    async def start(self) -> None:
        """Start idle watcher and schedule manager."""
        await self._idle_watcher.start()
        await self._schedule_manager.start()
        logger.info("ProactiveService started")

    async def stop(self) -> None:
        """Stop idle watcher and schedule manager."""
        await self._idle_watcher.stop()
        await self._schedule_manager.stop()
        logger.info("ProactiveService stopped")

    async def trigger_proactive(
        self,
        connection_id: UUID,
        trigger_type: str,
        prompt_key: str | None = None,
        context: str | None = None,
        idle_seconds: int | None = None,
    ) -> dict[str, str]:
        """Common proactive trigger execution flow.

        Returns:
            {"status": "triggered", "turn_id": "..."} on success,
            {"status": "skipped", "reason": "..."} if blocked.
        """
        # 1. Check connection exists
        conn = self._ws_manager.connections.get(connection_id)
        if conn is None or conn.is_closing:
            return {"status": "skipped", "reason": "connection not found"}

        # 2. Check no active turn
        mp = conn.message_processor
        if not mp or mp._current_turn_id is not None:
            return {"status": "skipped", "reason": "active turn in progress"}

        # 3. Idle recheck — connection may have become active while we were waiting
        now = time.time()
        if trigger_type == "idle":
            timeout = self._persona_overrides.get("default", self._config.idle_timeout_seconds)
            if now - conn.last_user_message_at < timeout:
                return {"status": "skipped", "reason": "connection became active"}

        # 4. Cooldown check
        last_at = self._last_proactive_at.get(connection_id, 0)
        if now - last_at < self._config.cooldown_seconds:
            remaining = int(self._config.cooldown_seconds - (now - last_at))
            return {
                "status": "skipped",
                "reason": f"cooldown active ({remaining}s remaining)",
            }

        # 5. Render prompt
        effective_key = prompt_key or trigger_type
        current_time = datetime.now().strftime("%H:%M:%S")
        prompt_text = self._prompt_loader.render(
            effective_key,
            idle_seconds=idle_seconds or 0,
            current_time=current_time,
            context=context or "",
        )

        # 6. Stream agent response + forward to client
        try:
            from langchain_core.messages import SystemMessage

            agent_stream = self._agent_service.stream(
                messages=[SystemMessage(content=prompt_text)],
                session_id=str(connection_id),
                persona_id="",  # no persona injection for proactive
                user_id=conn.user_id or "unknown",
                agent_id="proactive",
                is_new_session=False,
            )

            turn_id: str | None = None
            websocket = conn.websocket
            async for event in agent_stream:
                event["proactive"] = True
                if event.get("type") == "stream_start":
                    turn_id = event.get("turn_id", "")
                # Forward event directly to client
                event_json = json.dumps(event, default=str)
                await websocket.send_text(event_json)

            self._last_proactive_at[connection_id] = time.time()
            logger.info(
                f"Proactive {trigger_type} triggered for {connection_id} "
                f"(turn_id={turn_id})"
            )
            return {"status": "triggered", "turn_id": turn_id or ""}

        except Exception as exc:
            logger.exception(
                f"Proactive trigger failed for {connection_id}: {exc}"
            )
            return {"status": "skipped", "reason": f"error: {exc}"}

    def on_user_message(self, connection_id: UUID) -> None:
        """Called when a user sends a message — resets idle tracking."""
        self._idle_watcher.reset_connection(connection_id)
```

- [ ] **Step 4: Run tests**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/services/proactive_service/test_proactive_service.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/proactive_service/proactive_service.py tests/services/proactive_service/test_proactive_service.py
git commit -m "feat: add ProactiveService orchestrator with trigger flow"
```

---

## Task 9: Service registration (service_manager + main.py + __init__.py)

**Files:**
- Modify: `src/services/service_manager.py`
- Modify: `src/main.py`
- Update: `src/services/proactive_service/__init__.py`

- [ ] **Step 1: Update proactive_service __init__.py**

Update `src/services/proactive_service/__init__.py`:

```python
"""Proactive talking service — AI-initiated conversation triggers."""

from src.services.proactive_service.proactive_service import ProactiveService

__all__ = ["ProactiveService"]
```

- [ ] **Step 2: Add initializer to service_manager.py**

Add at the bottom of `src/services/service_manager.py`, before any if-main block:

```python
# -- Proactive Service --
_proactive_service_instance: "ProactiveService | None" = None


def get_proactive_service() -> "ProactiveService | None":
    return _proactive_service_instance


def initialize_proactive_service(
    ws_manager: Any,
    agent_service: Any,
    config_path: str | Path | None = None,
) -> "ProactiveService":
    """Build ProactiveService from YAML configuration."""
    global _proactive_service_instance

    from src.services.proactive_service.config import ProactiveConfig
    from src.services.proactive_service.proactive_service import ProactiveService

    proactive_cfg_dict = _load_service_yaml(
        service_name="Proactive",
        default_config_path=_BASE_YAML / "services.yml",
        config_key="proactive",
        config_path=config_path,
    )

    # Extract persona overrides from personas.yml
    persona_overrides: dict[str, int] = {}
    try:
        personas_path = _BASE_YAML / "personas.yml"
        if personas_path.exists():
            with open(personas_path, encoding="utf-8") as f:
                personas_data = yaml.safe_load(f) or {}
            for pid, pdata in personas_data.get("personas", {}).items():
                if "idle_timeout_seconds" in pdata:
                    persona_overrides[pid] = pdata["idle_timeout_seconds"]
    except Exception:
        logger.exception("Failed to load persona idle_timeout overrides")

    # Remove schedule dicts → ScheduleEntry objects handled by Pydantic
    config = ProactiveConfig(**proactive_cfg_dict)

    _proactive_service_instance = ProactiveService(
        config=config,
        ws_manager=ws_manager,
        agent_service=agent_service,
        persona_overrides=persona_overrides,
    )
    logger.info("ProactiveService initialized")
    return _proactive_service_instance
```

- [ ] **Step 3: Register in main.py lifespan**

In `src/main.py`, in the `_startup()` function, after the sweep service block (around line 164), add:

```python
            # Proactive talking service
            proactive_service = None
            try:
                from src.services.service_manager import initialize_proactive_service
                from src.services.websocket_service.manager import (
                    websocket_manager as _ws_mgr,
                )

                agent_svc = get_agent_service()
                if agent_svc is not None:
                    proactive_service = initialize_proactive_service(
                        ws_manager=_ws_mgr,
                        agent_service=agent_svc,
                        config_path=svc_config,
                    )
                    await proactive_service.start()
                    logger.info("Proactive service started")
                else:
                    logger.warning(
                        "Proactive service skipped: agent service not available"
                    )
            except Exception:
                logger.exception("Failed to start proactive service")
```

Update `_startup()` return to include proactive_service. Change return type and shutdown accordingly:

- Return `(sweep_service, proactive_service)` tuple
- In `_shutdown()`, add proactive service stop before sweep stop
- Update `lifespan()` to unpack the tuple

- [ ] **Step 4: Verify the app still starts**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/ -m "not slow and not e2e" -x -q
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/proactive_service/__init__.py src/services/service_manager.py src/main.py
git commit -m "feat: register ProactiveService in lifespan"
```

---

## Task 10: Webhook endpoint (Phase 3)

**Files:**
- Create: `src/models/proactive.py`
- Create: `src/api/routes/proactive.py`
- Modify: `src/api/routes/__init__.py`
- Test: `tests/api/test_proactive_route.py`

- [ ] **Step 1: Write failing test**

Create `tests/api/test_proactive_route.py`:

```python
"""Tests for POST /v1/proactive/trigger endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.proactive import router
from src.models.proactive import ProactiveTriggerRequest


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestProactiveTriggerEndpoint:
    def test_missing_session_id_returns_422(self, client):
        resp = client.post("/v1/proactive/trigger", json={"trigger_type": "webhook"})
        assert resp.status_code == 422

    @patch("src.api.routes.proactive.get_proactive_service")
    def test_service_not_available_returns_503(self, mock_get, client):
        mock_get.return_value = None
        resp = client.post(
            "/v1/proactive/trigger",
            json={"session_id": "test-session", "trigger_type": "webhook"},
        )
        assert resp.status_code == 503

    @patch("src.api.routes.proactive.get_proactive_service")
    def test_successful_trigger(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.trigger_proactive = AsyncMock(
            return_value={"status": "triggered", "turn_id": "t1"}
        )
        mock_get.return_value = mock_svc

        # Need to mock ws_manager to find connection by session_id
        mock_svc._ws_manager = MagicMock()

        resp = client.post(
            "/v1/proactive/trigger",
            json={"session_id": "test-session", "trigger_type": "webhook"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("triggered", "skipped")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/api/test_proactive_route.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create Pydantic models**

Create `src/models/proactive.py`:

```python
"""Pydantic models for proactive talking webhook API."""

from pydantic import BaseModel, Field


class ProactiveTriggerRequest(BaseModel):
    """POST /v1/proactive/trigger request body."""

    session_id: str = Field(..., description="Target session/connection ID")
    trigger_type: str = Field(default="webhook", description="Trigger type identifier")
    prompt_key: str | None = Field(
        default=None, description="Prompt template key override"
    )
    context: str | None = Field(
        default=None, description="Additional context injected into prompt"
    )


class ProactiveTriggerResponse(BaseModel):
    """POST /v1/proactive/trigger response body."""

    status: str = Field(..., description="'triggered' or 'skipped'")
    turn_id: str | None = Field(default=None, description="Turn ID if triggered")
    reason: str | None = Field(default=None, description="Skip reason if skipped")
```

- [ ] **Step 4: Create route**

Create `src/api/routes/proactive.py`:

```python
"""Proactive talking webhook endpoint."""

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.models.proactive import ProactiveTriggerRequest, ProactiveTriggerResponse
from src.services.service_manager import get_proactive_service

router = APIRouter(prefix="/v1/proactive", tags=["Proactive"])


@router.post(
    "/trigger",
    response_model=ProactiveTriggerResponse,
    summary="Trigger proactive talk for a session",
    responses={
        200: {"description": "Trigger executed or skipped"},
        503: {"description": "Proactive service not available"},
    },
)
async def trigger_proactive(request: ProactiveTriggerRequest) -> JSONResponse:
    """Trigger a proactive talk for the specified session."""
    svc = get_proactive_service()
    if svc is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "skipped", "reason": "proactive service not available"},
        )

    # Find connection by session_id (match against connection_id strings)
    connection_id: UUID | None = None
    for cid, conn in svc._ws_manager.connections.items():
        if str(cid) == request.session_id:
            connection_id = cid
            break

    if connection_id is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "skipped", "reason": "session not found"},
        )

    result = await svc.trigger_proactive(
        connection_id=connection_id,
        trigger_type=request.trigger_type,
        prompt_key=request.prompt_key,
        context=request.context,
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=result)
```

- [ ] **Step 5: Register router in __init__.py**

In `src/api/routes/__init__.py`, add:

```python
from src.api.routes import callback, ltm, proactive, slack, stm, tts, websocket
```

And:

```python
router.include_router(proactive.router)
```

- [ ] **Step 6: Run tests**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && uv run pytest tests/api/test_proactive_route.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/models/proactive.py src/api/routes/proactive.py src/api/routes/__init__.py tests/api/test_proactive_route.py
git commit -m "feat: add POST /v1/proactive/trigger webhook endpoint"
```

---

## Task 11: E2E Tests

**Files:**
- Create: `tests/e2e/test_proactive_e2e.py`
- Modify: `yaml_files/services.e2e.yml` (if exists, else create proactive section note)

- [ ] **Step 1: Add proactive config to E2E YAML**

Check if `yaml_files/services.e2e.yml` exists. Add `proactive` section with short timeouts:

```yaml
proactive:
  idle_timeout_seconds: 3
  cooldown_seconds: 5
  watcher_interval_seconds: 1
  schedules: []
```

- [ ] **Step 2: Create E2E tests**

Create `tests/e2e/test_proactive_e2e.py`:

```python
"""E2E tests for proactive talking feature.

Requires: FASTAPI_URL env var pointing to a running backend with proactive config.
    FASTAPI_URL=http://127.0.0.1:7123 uv run pytest -m e2e tests/e2e/test_proactive_e2e.py --tb=long
"""

import asyncio
import json

import httpx
import pytest
import websockets

TOKEN = "demo-token"
AGENT_ID = "e2e-agent"
USER_ID = "e2e-user"
CONNECT_TIMEOUT = 10
RECV_TIMEOUT = 30.0


@pytest.mark.e2e
class TestProactiveWebhookE2E:
    async def test_webhook_trigger_sends_proactive_message(self, e2e_session):
        """POST /v1/proactive/trigger → WS receives proactive-tagged events."""
        base_url = e2e_session["base_url"]
        ws_url = e2e_session["ws_url"]

        async with websockets.connect(
            ws_url,
            open_timeout=CONNECT_TIMEOUT,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            # Authorize
            await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))
            auth_response = None
            connection_id = None

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                data = json.loads(raw)
                if data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue
                if data.get("type") == "authorize_success":
                    connection_id = data.get("connection_id")
                    break
                if data.get("type") == "authorize_error":
                    pytest.fail(f"Auth failed: {data}")

            assert connection_id is not None

            # Trigger proactive via webhook
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    f"{base_url}/v1/proactive/trigger",
                    json={
                        "session_id": connection_id,
                        "trigger_type": "webhook",
                        "context": "E2E test trigger",
                    },
                )
                assert resp.status_code == 200
                trigger_result = resp.json()

            if trigger_result.get("status") == "skipped":
                pytest.skip(f"Trigger skipped: {trigger_result.get('reason')}")

            # Collect proactive events
            events = []
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                    events.append(data)
                    if data.get("type") == "stream_end":
                        break
            except TimeoutError:
                pytest.fail(
                    f"Timed out waiting for proactive stream_end. Events: {events}"
                )

            # Verify proactive tag
            event_types = [e["type"] for e in events]
            assert "stream_start" in event_types
            assert "stream_end" in event_types

            stream_start = next(e for e in events if e["type"] == "stream_start")
            assert stream_start.get("proactive") is True


@pytest.mark.e2e
class TestProactiveIdleE2E:
    async def test_idle_triggers_proactive_message(self, e2e_session):
        """Connect → wait idle_timeout → receive proactive message."""
        ws_url = e2e_session["ws_url"]

        async with websockets.connect(
            ws_url,
            open_timeout=CONNECT_TIMEOUT,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(json.dumps({"type": "authorize", "token": TOKEN}))

            # Wait for auth
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                data = json.loads(raw)
                if data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue
                if data.get("type") == "authorize_success":
                    break

            # Wait for proactive message (E2E config: idle_timeout=3s, watcher_interval=1s)
            # Should receive within ~5 seconds
            events = []
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                    events.append(data)
                    if data.get("type") == "stream_end":
                        break
            except TimeoutError:
                if not events:
                    pytest.fail(
                        "No proactive message received within 15s idle period"
                    )

            if events:
                event_types = [e["type"] for e in events]
                assert "stream_start" in event_types
                stream_start = next(
                    e for e in events if e["type"] == "stream_start"
                )
                assert stream_start.get("proactive") is True
```

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_proactive_e2e.py yaml_files/services.e2e.yml
git commit -m "test: add E2E tests for proactive talking"
```

---

## Task 12: Lint, full test run, and TODO update

- [ ] **Step 1: Run linter**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && make lint
```

Fix any issues.

- [ ] **Step 2: Run full unit test suite**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && make test
```

Expected: All PASS

- [ ] **Step 3: Run E2E tests (if backend available)**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend && make e2e
```

- [ ] **Step 4: Update TODO.md**

Mark proactive talking Phase 1, 2, 3 as `cc:DONE` in `TODO.md`. Add future TODOs:

```
- [ ] Idle 트리거 반복 모드 (cc:TODO)
- [ ] Idle 트리거 조건부 모드 (cc:TODO)
- [ ] 런타임 스케줄 CRUD API (cc:TODO)
- [ ] Webhook 인증 (cc:TODO)
- [ ] Broadcast 모드 (cc:TODO)
- [ ] EventBus 기반 아키텍처 전환 (cc:TODO)
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete proactive talking (Phase 1/2/3)"
```
