# HITL Built-in Middleware Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 커스텀 `HitLMiddleware` / `ToolGateMiddleware` / `ToolRegistry` 를 LangChain 빌트인 `HumanInTheLoopMiddleware` + `FileManagementToolkit` + 신규 `EditFileTool` 로 교체. WebSocket 페이로드는 빌트인 shape 1:1 반영 (FE 미작업 이점 활용).

**Architecture:** 단일 PR(big-bang), 내부는 7개 원자적 태스크. Task 1 (MongoDB checkpointer 호환 스파이크)이 블로커 — 실패 시 재논의.

**Tech Stack:** Python 3.13, FastAPI, LangChain `create_agent` + 빌트인 `HumanInTheLoopMiddleware`, LangGraph 1.1+, `langgraph-checkpoint-mongodb` `MongoDBSaver` (sync, 현행), `langchain_community.agent_toolkits.FileManagementToolkit`, Pydantic V2, pytest, loguru.

**Spec:** `docs/superpowers/specs/2026-04-18-hitl-builtin-middleware-migration-design.md`

---

## File Map

### 신규
- `tests/spike/test_hitl_mongodb_checkpointer.py` (Task 1)
- `tests/unit/test_edit_file_tool.py` (Task 3)

### 재작성
- `src/services/agent_service/tools/builtin/filesystem_tools.py` (Task 3)
- `src/models/websocket.py` — HITL 메시지 부분만 교체 (Task 2)

### 수정
- `src/services/agent_service/openai_chat_agent.py` (Task 4)
- `src/services/websocket_service/manager/handlers.py` (Task 4)
- `src/services/websocket_service/message_processor/processor.py` (Task 4)
- `src/services/websocket_service/message_processor/event_handlers.py` (Task 4)
- `src/services/agent_service/middleware/__init__.py` (Task 6, exports 정리)
- `src/configs/agent/openai_chat_agent.py` (Task 6, `ToolConfig` 제거 + `filesystem_root_dir` 추가)
- `yaml_files/services.yml`, `services.docker.yml`, `services.e2e.yml` (Task 6)
- `tests/unit/test_hitl_models.py` (Task 2)
- `tests/unit/test_hitl_agent_stream.py` (Task 4)
- `tests/unit/test_hitl_event_handling.py` (Task 4)
- `tests/e2e/test_hitl_e2e.py` (Task 5)
- `docs/data_flow/agent/HITL_GATE_FLOW.md` (Task 7)
- `docs/known_issues/KNOWN_ISSUES.md` (Task 7)

### 삭제
- `src/services/agent_service/middleware/hitl_middleware.py`
- `src/services/agent_service/middleware/tool_gate_middleware.py`
- `src/services/agent_service/tools/registry.py`
- `src/services/agent_service/tools/builtin/shell_tools.py`
- `src/services/agent_service/tools/builtin/search_tools.py`
- `tests/unit/test_hitl_middleware.py`
- `tests/services/agent_service/middleware/test_tool_gate_middleware.py`
- `tests/services/agent_service/tools/test_registry.py`
- `docs/todo/human-in-the-loop.md`

---

## Task 1: MongoDB Checkpointer HITL Compatibility Spike

**Goal:** 현행 sync `MongoDBSaver` 가 `HumanInTheLoopMiddleware` 의 interrupt/resume 라이프사이클과 호환되는지 검증. 실패 시 폴백 단계 수행.

**Files:**
- Create: `tests/spike/test_hitl_mongodb_checkpointer.py`
- Reference (참조만): `tests/spike/test_interrupt_in_middleware.py` (기존 유사 스파이크)
- Reference: `src/services/agent_service/openai_chat_agent.py:127-137` (현행 checkpointer 초기화)

- [ ] **Step 1: 스파이크 테스트 작성**

Create `tests/spike/test_hitl_mongodb_checkpointer.py`:

```python
"""Spike: verify MongoDBSaver (sync) + HumanInTheLoopMiddleware interrupt/resume cycle.

Blocker for HITL built-in middleware migration. If this fails, the
migration plan needs to pivot (async saver swap or dependency bump).
"""

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.tools import tool
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import Command
from pymongo import MongoClient

from src.configs.settings import get_settings


@tool
def mutating_tool(payload: str) -> str:
    """Fake mutating tool that must be gated by HITL."""
    return f"applied: {payload}"


@pytest.mark.spike
@pytest.mark.asyncio
async def test_mongodb_saver_supports_hitl_interrupt_and_resume():
    """Agent with MongoDBSaver pauses on mutating_tool, resumes on approve."""
    settings = get_settings()
    mongo_client = MongoClient(settings.mongo.connection_string)
    checkpointer = MongoDBSaver(client=mongo_client)

    agent = create_agent(
        model=settings.llm.model_name,  # any configured chat model
        tools=[mutating_tool],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={"mutating_tool": True}),
        ],
    )

    config = {"configurable": {"thread_id": "spike-mongo-hitl"}}
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Please call mutating_tool with payload='x'"}]},
        config=config,
    )

    # Graph must be suspended at interrupt, not completed
    interrupts = result.get("__interrupt__") or []
    assert len(interrupts) == 1, f"Expected 1 interrupt, got {len(interrupts)}"
    value = interrupts[0].value
    assert "action_requests" in value
    assert value["action_requests"][0]["name"] == "mutating_tool"

    # Resume with approve — same thread_id, Mongo checkpoint must be readable
    resumed = await agent.ainvoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
    )
    assert "applied: x" in str(resumed["messages"][-1].content)
```

- [ ] **Step 2: 스파이크 실행 — 현행 sync saver**

Run: `uv run pytest tests/spike/test_hitl_mongodb_checkpointer.py -v -s`

**분기:**
- PASS → Step 5 로 점프 (커밋).
- FAIL (saver 타입 오류 등) → Step 3.

- [ ] **Step 3: 폴백 ① AsyncMongoDBSaver 시도**

테스트 파일 내 import·생성을 교체:

```python
from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
from motor.motor_asyncio import AsyncIOMotorClient

# ... inside test:
mongo_client = AsyncIOMotorClient(settings.mongo.connection_string)
checkpointer = AsyncMongoDBSaver(client=mongo_client)
```

Run: `uv run pytest tests/spike/test_hitl_mongodb_checkpointer.py -v -s`

**분기:**
- PASS → Step 4 스킵하고 Step 5 로, **단 Task 4 에서 `openai_chat_agent.py:131-133` 도 `AsyncMongoDBSaver` + `AsyncIOMotorClient` 로 교체해야 함**. `plans/` 문서에 메모 남길 것.
- FAIL → Step 4.

- [ ] **Step 4: 폴백 ② `langgraph-checkpoint-mongodb` 버전 bump**

`pyproject.toml` 의 `langgraph-checkpoint-mongodb` 핀을 최신 minor 로 올리고:

```bash
uv lock --upgrade-package langgraph-checkpoint-mongodb
uv sync
```

재실행: `uv run pytest tests/spike/test_hitl_mongodb_checkpointer.py -v -s`

**분기:**
- PASS → Step 5.
- FAIL → **중단**. `docs/superpowers/plans/` 에 실패 이유 메모하고 유저에게 보고. 이후 태스크 진행 불가.

- [ ] **Step 5: 스파이크 커밋**

```bash
git add tests/spike/test_hitl_mongodb_checkpointer.py
# Step 3/4 에서 바꾼 게 있으면 pyproject.toml, uv.lock 도 포함
git commit -m "test: spike MongoDB checkpointer + HumanInTheLoopMiddleware compatibility"
```

---

## Task 2: WebSocket HITL Pydantic Models

**Goal:** `HitLRequestMessage` / `HitLResponseMessage` 를 빌트인 list-based shape 로 교체. TDD.

**Files:**
- Modify: `src/models/websocket.py` (HitL 섹션만; `request_id`/`approved` 필드 제거, `action_requests` / `decisions` 추가)
- Rewrite: `tests/unit/test_hitl_models.py`

- [ ] **Step 1: 실패 테스트 작성**

Rewrite `tests/unit/test_hitl_models.py`:

```python
"""Tests for HITL WebSocket Pydantic models (built-in shape)."""

import pytest
from pydantic import ValidationError

from src.models.websocket import (
    HitLActionRequest,
    HitLDecision,
    HitLEditedAction,
    HitLRequestMessage,
    HitLResponseMessage,
    HitLReviewConfig,
    MessageType,
)


def test_hitl_action_request_valid():
    ar = HitLActionRequest(
        name="write_file", arguments={"file_path": "a.txt", "text": "hi"}, description="desc"
    )
    assert ar.name == "write_file"


def test_hitl_review_config_rejects_unknown_decision():
    with pytest.raises(ValidationError):
        HitLReviewConfig(action_name="write_file", allowed_decisions=["bogus"])


def test_hitl_request_message_shape():
    msg = HitLRequestMessage(
        session_id="s1",
        action_requests=[
            HitLActionRequest(name="write_file", arguments={}, description="d"),
        ],
        review_configs=[
            HitLReviewConfig(action_name="write_file", allowed_decisions=["approve", "reject"]),
        ],
    )
    assert msg.type == MessageType.HITL_REQUEST


def test_hitl_decision_approve_allows_bare():
    d = HitLDecision(type="approve")
    assert d.edited_action is None and d.message is None


def test_hitl_decision_edit_requires_edited_action():
    with pytest.raises(ValidationError):
        HitLDecision(type="edit")


def test_hitl_decision_edit_with_edited_action():
    d = HitLDecision(
        type="edit",
        edited_action=HitLEditedAction(name="write_file", args={"file_path": "b.txt", "text": "hi"}),
    )
    assert d.edited_action.name == "write_file"


def test_hitl_decision_approve_rejects_message_or_edited_action():
    with pytest.raises(ValidationError):
        HitLDecision(type="approve", message="no")
    with pytest.raises(ValidationError):
        HitLDecision(
            type="approve",
            edited_action=HitLEditedAction(name="x", args={}),
        )


def test_hitl_decision_reject_allows_optional_message():
    d = HitLDecision(type="reject", message="unsafe path")
    assert d.message == "unsafe path"


def test_hitl_response_message_list_shape():
    msg = HitLResponseMessage(decisions=[HitLDecision(type="approve")])
    assert msg.type == MessageType.HITL_RESPONSE
    assert len(msg.decisions) == 1
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/unit/test_hitl_models.py -v`
Expected: 전체 FAIL (`HitLActionRequest`, `HitLDecision`, `HitLEditedAction`, `HitLReviewConfig` 미정의, 그리고 `HitLRequestMessage` / `HitLResponseMessage` 가 구 필드 사용).

- [ ] **Step 3: 신 모델 구현**

Edit `src/models/websocket.py`:

1. 파일 상단 import 에 `Literal`, `model_validator` 추가 (없으면):
```python
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
```

2. 기존 `class HitLResponseMessage` (144-149) 블록 교체:
```python
class HitLEditedAction(BaseModel):
    """Replacement tool call args when user picks 'edit'."""
    name: str
    args: dict[str, Any]


class HitLDecision(BaseModel):
    """Single approve/edit/reject decision for one action_request."""
    type: Literal["approve", "edit", "reject"]
    edited_action: HitLEditedAction | None = None
    message: str | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> "HitLDecision":
        if self.type == "edit" and self.edited_action is None:
            raise ValueError("edit decision requires edited_action")
        if self.type == "approve" and (self.edited_action or self.message):
            raise ValueError("approve decision must not carry edited_action or message")
        return self


class HitLResponseMessage(BaseMessage):
    """Client message: one decision per server-issued action_request, same order."""
    type: MessageType = MessageType.HITL_RESPONSE
    decisions: list[HitLDecision]
```

3. 기존 `class HitLRequestMessage` (220-227) 블록 교체:
```python
class HitLActionRequest(BaseModel):
    """One tool call awaiting human review."""
    name: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(..., description="Tool call arguments")
    description: str = Field(..., description="Human-readable description for UI")


class HitLReviewConfig(BaseModel):
    """Allowed decisions for one action_request (parallel to action_requests)."""
    action_name: str
    allowed_decisions: list[Literal["approve", "edit", "reject"]]


class HitLRequestMessage(BaseMessage):
    """Server message: list of pending tool calls requiring human review."""
    type: MessageType = MessageType.HITL_REQUEST
    session_id: str
    action_requests: list[HitLActionRequest]
    review_configs: list[HitLReviewConfig]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_hitl_models.py -v`
Expected: PASS (전부).

- [ ] **Step 5: 커밋**

```bash
git add src/models/websocket.py tests/unit/test_hitl_models.py
git commit -m "feat(ws): add list-based HITL message schemas for built-in middleware"
```

---

## Task 3: Filesystem Tools Rewrite (Toolkit + EditFileTool)

**Goal:** 커스텀 3-tool 래퍼를 `FileManagementToolkit` 7-tool + 신규 `EditFileTool` 로 교체. 실제 디스크 쓰기 유지, sandbox `root_dir` 강제.

**Files:**
- Rewrite: `src/services/agent_service/tools/builtin/filesystem_tools.py`
- Create: `tests/unit/test_edit_file_tool.py`

- [ ] **Step 1: EditFileTool 테스트 작성**

Create `tests/unit/test_edit_file_tool.py`:

```python
"""Tests for EditFileTool: unique-match edit with sandbox guard."""

from pathlib import Path

import pytest


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.asyncio
async def test_edit_unique_match(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    (sandbox / "a.txt").write_text("hello world\n")
    tool = EditFileTool(root_dir=str(sandbox))

    result = await tool._arun(file_path="a.txt", old_string="world", new_string="yuri")

    assert "Edited a.txt" in result
    assert (sandbox / "a.txt").read_text() == "hello yuri\n"


@pytest.mark.asyncio
async def test_edit_absent_match(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    (sandbox / "a.txt").write_text("hello\n")
    tool = EditFileTool(root_dir=str(sandbox))

    result = await tool._arun(file_path="a.txt", old_string="XXX", new_string="YYY")

    assert "not found" in result
    assert (sandbox / "a.txt").read_text() == "hello\n"


@pytest.mark.asyncio
async def test_edit_ambiguous_match(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    (sandbox / "a.txt").write_text("foo foo\n")
    tool = EditFileTool(root_dir=str(sandbox))

    result = await tool._arun(file_path="a.txt", old_string="foo", new_string="bar")

    assert "matches 2 times" in result
    assert (sandbox / "a.txt").read_text() == "foo foo\n"


@pytest.mark.asyncio
async def test_edit_rejects_absolute_path(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    tool = EditFileTool(root_dir=str(sandbox))
    result = await tool._arun(file_path="/etc/passwd", old_string="a", new_string="b")

    assert "must be relative" in result


@pytest.mark.asyncio
async def test_edit_rejects_traversal(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import EditFileTool

    outside = sandbox.parent / "outside.txt"
    outside.write_text("secret\n")
    try:
        tool = EditFileTool(root_dir=str(sandbox))
        result = await tool._arun(file_path="../outside.txt", old_string="secret", new_string="LEAKED")
        assert "escapes sandbox" in result
        assert outside.read_text() == "secret\n"
    finally:
        outside.unlink(missing_ok=True)


def test_get_filesystem_tools_returns_eight_tools(sandbox: Path):
    from src.services.agent_service.tools.builtin.filesystem_tools import get_filesystem_tools

    tools = get_filesystem_tools(root_dir=str(sandbox))
    names = {t.name for t in tools}
    expected = {
        "copy_file", "delete_file", "file_search", "move_file",
        "read_file", "write_file", "list_directory", "edit_file",
    }
    assert names == expected
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/unit/test_edit_file_tool.py -v`
Expected: FAIL (`EditFileTool` 미정의, 또는 현행 `get_filesystem_tools` 가 3툴만 반환).

- [ ] **Step 3: filesystem_tools.py 전체 재작성**

Overwrite `src/services/agent_service/tools/builtin/filesystem_tools.py`:

```python
"""Filesystem tools: FileManagementToolkit (disk-backed) + EditFileTool."""

import asyncio
from pathlib import Path

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field


def get_filesystem_tools(root_dir: str) -> list[BaseTool]:
    """Return FileManagementToolkit's 7 tools + EditFileTool, all scoped to root_dir."""
    toolkit_tools = FileManagementToolkit(root_dir=root_dir).get_tools()
    return [*toolkit_tools, EditFileTool(root_dir=root_dir)]


class _EditFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path within root_dir")
    old_string: str = Field(..., description="Exact substring to replace (must occur exactly once)")
    new_string: str = Field(..., description="Replacement string")


class EditFileTool(BaseTool):
    """Edit a file by replacing exactly one occurrence of old_string with new_string."""

    name: str = "edit_file"
    description: str = (
        "Replace a unique substring in a text file. "
        "Fails if old_string is absent or matches more than once."
    )
    args_schema: type[_EditFileInput] = _EditFileInput
    root_dir: str

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use async invocation")

    async def _arun(self, file_path: str, old_string: str, new_string: str) -> str:
        if Path(file_path).is_absolute():
            return "file_path must be relative to the sandbox root."
        root = Path(self.root_dir).resolve()
        target = (root / file_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return "file_path escapes sandbox root."

        content = await asyncio.to_thread(target.read_text, encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return f"old_string not found in {file_path}."
        if count > 1:
            return f"old_string matches {count} times in {file_path}; provide more context."
        await asyncio.to_thread(
            target.write_text, content.replace(old_string, new_string, 1), encoding="utf-8"
        )
        logger.info(f"edit_file: {file_path} (1 replacement)")
        return f"Edited {file_path}."
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/test_edit_file_tool.py -v`
Expected: 6 PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/services/agent_service/tools/builtin/filesystem_tools.py tests/unit/test_edit_file_tool.py
git commit -m "feat(tools): replace filesystem wrapper with FileManagementToolkit + EditFileTool"
```

---

## Task 4: Agent Service + WebSocket Handlers Atomic Swap

**Goal:** 한 커밋에 아래 전부 — 구 payload shape 와 신 파서 공존 불가이므로 원자적.
1. `HitLMiddleware` / `ToolGateMiddleware` 제거 + `HumanInTheLoopMiddleware` 추가 + `_build_interrupt_on` helper.
2. `__interrupt__` 파서 신 shape 로 재작성.
3. `resume_after_approval()` 신 시그니처 (`decisions: list[dict]`).
4. `handlers.py::handle_hitl_response` 신 payload 파싱 + 신 시그니처 호출.
5. `processor.py:310` deny 호출 신 시그니처.
6. `event_handlers.py` hitl_request 이벤트 — `interrupt_id` 대신 `action_requests` 개수 저장.

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py`
- Modify: `src/services/websocket_service/manager/handlers.py` (줄 283-348)
- Modify: `src/services/websocket_service/message_processor/processor.py` (줄 303-317)
- Modify: `src/services/websocket_service/message_processor/event_handlers.py` (줄 63-74)
- Rewrite: `tests/unit/test_hitl_agent_stream.py`
- Rewrite: `tests/unit/test_hitl_event_handling.py`

- [ ] **Step 1: 에이전트 스트림 파서 테스트 작성**

Overwrite `tests/unit/test_hitl_agent_stream.py`:

```python
"""Tests for OpenAIChatAgent __interrupt__ parsing (built-in HITL shape)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class _FakeAgent:
    def __init__(self, chunks):
        self._chunks = chunks

    def astream(self, *_, **__):
        async def gen():
            for c in self._chunks:
                yield c
        return gen()


@pytest.mark.asyncio
async def test_interrupt_single_action_request_forwarded_as_list():
    from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

    interrupt_value = {
        "action_requests": [
            {"name": "write_file", "arguments": {"file_path": "a.txt"}, "description": "desc"},
        ],
        "review_configs": [
            {"action_name": "write_file", "allowed_decisions": ["approve", "edit", "reject"]},
        ],
    }
    chunks = [
        ("updates", {"__interrupt__": [SimpleNamespace(value=interrupt_value)]}),
    ]
    agent = OpenAIChatAgent.__new__(OpenAIChatAgent)
    agent.agent = _FakeAgent(chunks)

    events = []
    async for ev in agent._consume_astream(_FakeAgent(chunks).astream(), "s1"):
        events.append(ev)

    assert len(events) == 1
    assert events[0]["type"] == "hitl_request"
    assert events[0]["session_id"] == "s1"
    assert events[0]["action_requests"] == interrupt_value["action_requests"]
    assert events[0]["review_configs"] == interrupt_value["review_configs"]


@pytest.mark.asyncio
async def test_interrupt_multi_action_requests_preserve_order():
    from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

    interrupt_value = {
        "action_requests": [
            {"name": "write_file", "arguments": {"file_path": "a"}, "description": "d1"},
            {"name": "delete_file", "arguments": {"file_path": "b"}, "description": "d2"},
        ],
        "review_configs": [
            {"action_name": "write_file", "allowed_decisions": ["approve", "reject"]},
            {"action_name": "delete_file", "allowed_decisions": ["approve", "reject"]},
        ],
    }
    chunks = [("updates", {"__interrupt__": [SimpleNamespace(value=interrupt_value)]})]
    agent = OpenAIChatAgent.__new__(OpenAIChatAgent)

    events = []
    async for ev in agent._consume_astream(_FakeAgent(chunks).astream(), "s2"):
        events.append(ev)

    assert events[0]["action_requests"][0]["name"] == "write_file"
    assert events[0]["action_requests"][1]["name"] == "delete_file"


def test_build_interrupt_on_matrix():
    from src.services.agent_service.openai_chat_agent import _build_interrupt_on

    mcp_names = {"mcp_tool_a", "mcp_tool_b"}
    matrix = _build_interrupt_on(mcp_names)

    # MCP + delegate_task + FS mutating — all True
    for name in mcp_names | {"delegate_task", "write_file", "copy_file", "move_file", "delete_file", "edit_file"}:
        assert matrix[name] is True

    # safe tools not in matrix
    for name in {"read_file", "list_directory", "file_search"}:
        assert name not in matrix
```

- [ ] **Step 2: event_handler 테스트 작성**

Overwrite `tests/unit/test_hitl_event_handling.py`:

```python
"""Tests for EventHandler.hitl_request handling (built-in shape)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.websocket_service.message_processor.models import TurnStatus


@pytest.mark.asyncio
async def test_hitl_request_sets_awaiting_approval_and_stores_count():
    from src.services.websocket_service.message_processor.event_handlers import EventHandler

    processor = MagicMock()
    processor.update_turn_status = AsyncMock()
    processor._put_event = AsyncMock()
    turn = MagicMock()
    turn.metadata = {}
    processor.turns = {"t1": turn}

    handler = EventHandler(processor)
    handler._signal_token_stream_closed = AsyncMock()
    handler._wait_for_token_queue = AsyncMock()

    async def stream():
        yield {
            "type": "hitl_request",
            "session_id": "s1",
            "action_requests": [
                {"name": "write_file", "arguments": {}, "description": "d"},
            ],
            "review_configs": [
                {"action_name": "write_file", "allowed_decisions": ["approve", "reject"]},
            ],
        }

    await handler.produce_agent_events("t1", stream())

    processor.update_turn_status.assert_awaited_with("t1", TurnStatus.AWAITING_APPROVAL)
    # 서버는 count 를 저장해 handle_hitl_response 의 decisions-count-mismatch 검증에 사용
    assert turn.metadata["pending_action_count"] == 1
    processor._put_event.assert_awaited()
```

- [ ] **Step 3: 실패 확인**

Run: `uv run pytest tests/unit/test_hitl_agent_stream.py tests/unit/test_hitl_event_handling.py -v`
Expected: 전체 FAIL.

- [ ] **Step 4: `openai_chat_agent.py` 수정**

`src/services/agent_service/openai_chat_agent.py`:

① 파일 상단 import 교체 — 구 middleware import 2줄(19-25) 삭제, 추가:
```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

from src.services.agent_service.middleware.delegate_middleware import (
    DelegateToolMiddleware,
)
```

② 파일 상단(클래스 밖)에 상수·helper 추가 (personas 로더 위):
```python
_FS_MUTATING_TOOLS = frozenset({
    "write_file", "copy_file", "move_file", "delete_file", "edit_file",
})


def _build_interrupt_on(mcp_tool_names: set[str]) -> dict[str, bool]:
    """All MCP tools + delegate_task + mutating FS tools require HITL approval."""
    return {
        **{name: True for name in mcp_tool_names},
        "delegate_task": True,
        **{name: True for name in _FS_MUTATING_TOOLS},
    }
```

③ `initialize_async` 내부 미들웨어 구성 블록(현재 줄 153-181) 교체:
```python
from src.services.agent_service.tools.builtin.filesystem_tools import (
    get_filesystem_tools,
)

custom_tools = list(self._mcp_tools)
profile_svc = get_user_profile_service()
if profile_svc is not None:
    custom_tools.append(UpdateUserProfileTool(service=profile_svc))

from src.configs.settings import get_settings
custom_tools.extend(get_filesystem_tools(root_dir=get_settings().agent.filesystem_root_dir))

self.agent = create_agent(
    model=self.llm,
    tools=custom_tools,
    state_schema=CustomAgentState,
    checkpointer=checkpointer,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on=_build_interrupt_on({t.name for t in self._mcp_tools}),
        ),
        DelegateToolMiddleware(),
        before_model(profile_retrieve_hook),
        before_model(summary_inject_hook),
        before_model(ltm_retrieve_hook),
        before_model(task_status_inject_hook),
        after_model(ltm_consolidation_hook),
        after_model(summary_consolidation_hook),
    ],
)
logger.info("Agent created successfully")
```

④ `_consume_astream` 내부 `__interrupt__` 블록(현재 줄 393-402) 교체:
```python
if data.get("__interrupt__"):
    interrupt_value = data["__interrupt__"][0].value
    yield {
        "type": "hitl_request",
        "session_id": session_id,
        "action_requests": interrupt_value["action_requests"],
        "review_configs": interrupt_value["review_configs"],
    }
    return
```

⑤ `resume_after_approval` 메서드(현재 줄 271-309) 전체 교체:
```python
async def resume_after_approval(
    self,
    session_id: str,
    decisions: list[dict],
    *,
    context: dict | None = None,
):
    """Resume graph with built-in HITL decisions list.

    decisions: list parallel to the interrupt's action_requests.
    Each entry: {"type": "approve"|"edit"|"reject", ...}.
    """
    from langgraph.types import Command

    config = {"configurable": {"thread_id": session_id}}
    astream_iter = self.agent.astream(
        Command(resume={"decisions": decisions}),
        config=config,
        stream_mode=["messages", "updates"],
        context=context,
    )
    async for event in self._consume_astream(astream_iter, session_id):
        if event["type"] == "final_response":
            new_chats = event["data"]
            content = new_chats[-1].content if new_chats else ""
            yield {
                "type": "stream_end",
                "turn_id": "",
                "session_id": session_id,
                "content": content,
                "new_chats": new_chats,
            }
        else:
            yield event
```

⑥ `stream` 메서드 내부 `had_hitl_request` 분기(현재 줄 240-256) 는 그대로 유지 — 이벤트 타입만 같으면 동작.

- [ ] **Step 5: `event_handlers.py` 수정**

`src/services/websocket_service/message_processor/event_handlers.py` 줄 63-74 교체:

```python
if event_type == "hitl_request":
    await self.processor.update_turn_status(
        turn_id, TurnStatus.AWAITING_APPROVAL
    )
    turn = self.processor.turns.get(turn_id)
    if turn is not None:
        turn.metadata["pending_action_count"] = len(event.get("action_requests", []))
    await self.processor._put_event(turn_id, event)
    await self._signal_token_stream_closed(turn_id)
    await self._wait_for_token_queue(turn_id)
    return  # Exit producer; graph is suspended at checkpoint
```

- [ ] **Step 6: `handlers.py` 수정**

`src/services/websocket_service/manager/handlers.py` 메서드 `handle_hitl_response` (줄 283-348) 전체 교체:

```python
async def handle_hitl_response(
    self,
    connection_id: UUID,
    message_data: dict,
    forward_events_fn,
) -> None:
    """Handle HITL decisions list from client for built-in HumanInTheLoopMiddleware."""
    from src.models.websocket import HitLResponseMessage

    connection_state = self.get_connection(connection_id)
    if not connection_state or not connection_state.message_processor:
        await self.send_message(
            connection_id, ErrorMessage(error="No active session", code=4004)
        )
        return

    processor = connection_state.message_processor
    turn_id = processor._current_turn_id
    if not turn_id:
        await self.send_message(
            connection_id,
            ErrorMessage(error="No active turn awaiting approval", code=4004),
        )
        return

    turn = processor.turns.get(turn_id)
    if not turn or turn.status != TurnStatus.AWAITING_APPROVAL:
        await self.send_message(
            connection_id,
            ErrorMessage(error="No pending approval request", code=4004),
        )
        return

    # Parse decisions via Pydantic (validates approve/edit/reject + shape)
    try:
        parsed = HitLResponseMessage.model_validate(
            {"type": "hitl_response", **message_data}
        )
    except Exception as e:
        await self.send_message(
            connection_id, ErrorMessage(error=f"Invalid hitl_response: {e}", code=4004)
        )
        return

    expected = turn.metadata.get("pending_action_count", 0)
    if len(parsed.decisions) != expected:
        await self.send_message(
            connection_id,
            ErrorMessage(
                error=f"decisions count mismatch: expected {expected}, got {len(parsed.decisions)}",
                code=4004,
            ),
        )
        return  # keep AWAITING_APPROVAL, allow client retry

    agent_service = get_agent_service()
    if not agent_service:
        await self.send_message(
            connection_id, ErrorMessage(error="Agent service unavailable")
        )
        return

    await processor.update_turn_status(turn_id, TurnStatus.PROCESSING)

    decisions_dicts = [d.model_dump(exclude_none=True) for d in parsed.decisions]
    agent_stream = agent_service.resume_after_approval(
        session_id=turn.session_id,
        decisions=decisions_dicts,
    )

    await processor.attach_agent_stream(turn_id, agent_stream)

    forward_task = asyncio.create_task(
        forward_events_fn(connection_id, turn_id),
        name=f"ws-forward-events-hitl-{turn_id}",
    )
    await processor.add_task_to_turn(turn_id, forward_task)
```

- [ ] **Step 7: `processor.py` 수정**

`src/services/websocket_service/message_processor/processor.py` 줄 303-317 교체:

```python
# If turn is awaiting HitL approval, send reject to clear graph checkpoint
if previous_status == TurnStatus.AWAITING_APPROVAL:
    from src.services.service_manager import get_agent_service

    agent_service = get_agent_service()
    if agent_service:
        session_id = turn.session_id
        count = turn.metadata.get("pending_action_count", 1)
        reject_decisions = [{"type": "reject"} for _ in range(count)]
        try:
            async for _ in agent_service.resume_after_approval(
                session_id=session_id, decisions=reject_decisions,
            ):
                pass
        except Exception:
            logger.warning(
                f"Failed to clear HitL checkpoint for turn {target_turn_id}"
            )
```

- [ ] **Step 8: 단위 테스트 실행**

Run:
```bash
uv run pytest tests/unit/test_hitl_agent_stream.py tests/unit/test_hitl_event_handling.py -v
```
Expected: PASS.

- [ ] **Step 9: Smoke — 서버 기동 확인**

Run: `make lint` → PASS (import 순서/미사용 정리).
Run: `uv run python -c "from src.main import create_app; create_app()"` → no errors.

- [ ] **Step 10: 커밋**

```bash
git add src/services/agent_service/openai_chat_agent.py \
        src/services/websocket_service/manager/handlers.py \
        src/services/websocket_service/message_processor/processor.py \
        src/services/websocket_service/message_processor/event_handlers.py \
        tests/unit/test_hitl_agent_stream.py \
        tests/unit/test_hitl_event_handling.py
git commit -m "feat(agent): swap to built-in HumanInTheLoopMiddleware with list-based HITL"
```

---

## Task 5: End-to-End Test Rewrite

**Goal:** §7 E2E 매트릭스 9개 시나리오 전부 실제 스택으로 검증.

**Files:**
- Rewrite: `tests/e2e/test_hitl_e2e.py`

- [ ] **Step 1: 신 E2E 작성 (9개 시나리오)**

Overwrite `tests/e2e/test_hitl_e2e.py` — 다음 9개 테스트 함수를 포함 (클래스 `TestHitLBuiltinFlow`):

1. `test_normal_chat_no_hitl_request` — `chat_message` → safe 응답 → `stream_end`, `hitl_request` 없음.
2. `test_safe_tool_no_hitl_request` — 유리에게 "read_file a.txt" 요청 → `hitl_request` 없음.
3. `test_write_file_approve` — write 요청 → `hitl_request` 수신 (`action_requests` 길이 1) → `hitl_response` `{decisions:[{type:"approve"}]}` → `stream_end`, 실제 파일 생성 확인.
4. `test_write_file_reject_with_message` — reject + message 전송 → agent 가 ToolMessage 받고 대체 응답 → `stream_end`. LLM 비결정성 → `pytest.skip` 패턴 (기존 테스트 line 240 참조).
5. `test_write_file_edit` — edit decision 으로 `edited_action.args.file_path` 바꿔서 재실행 → 수정된 경로에 파일 생성 확인.
6. `test_multi_parallel_tool_calls` — 프롬프트로 두 dangerous tool 유도 → `action_requests` 2개 → mixed decisions 응답 → 순서 보존 실행. LLM 비결정성 skip.
7. `test_decisions_count_mismatch_returns_error` — `action_requests` 1개인데 0개 decisions 전송 → `ErrorMessage(code=4004)` 수신, 턴 상태 유지, 재전송(1개 decisions) 성공.
8. `test_hitl_response_without_pending_approval` — chat 없이 바로 `hitl_response` 전송 → `ErrorMessage(code=4004)`.
9. `test_hitl_response_requires_authentication` — 인증 전 `hitl_response` → `ErrorMessage`.

각 시나리오의 프레임은 기존 `tests/e2e/test_hitl_e2e.py` 의 fixture (`e2e_session`, `collect_events_until_terminal`) 와 `terminal_types = {"stream_end","error","hitl_request"}` 패턴을 재사용. 구 `request_id` / `approved` 필드 사용하던 모든 코드 제거. 예시 — 시나리오 3:

```python
class TestHitLBuiltinFlow:
    @pytest.mark.asyncio
    async def test_write_file_approve(self, e2e_session):
        async for conn in e2e_session() as ws:
            await ws.send_json({
                "type": "chat_message",
                "content": "Please write 'hello' to a file named e2e_test.txt.",
                "user_id": "u", "agent_id": "yuri", "persona_id": "yuri",
                "tts_enabled": False,
            })

            events = await collect_events_until_terminal(
                ws, terminal_types={"hitl_request", "stream_end", "error"},
            )
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")

            assert "action_requests" in hitl
            assert len(hitl["action_requests"]) == 1
            assert hitl["action_requests"][0]["name"] == "write_file"

            await ws.send_json({
                "type": "hitl_response",
                "decisions": [{"type": "approve"}],
            })

            final = await collect_events_until_terminal(
                ws, terminal_types={"stream_end", "error"},
            )
            assert any(e["type"] == "stream_end" for e in final)

            sandbox = Path(settings.agent.filesystem_root_dir) / "e2e_test.txt"
            assert sandbox.exists()
            assert "hello" in sandbox.read_text()
            sandbox.unlink(missing_ok=True)
```

다른 시나리오도 동일 패턴으로 작성하되 payload·검증만 바꿈. 시나리오 4·6 에는 `if hitl is None: pytest.skip(...)` + `if len(action_requests) != 2: pytest.skip(...)` 추가.

- [ ] **Step 2: E2E 실행**

Run: `bash scripts/e2e.sh` (CLAUDE.md 강제 규칙).
Expected: 전체 시나리오 PASS 또는 비결정성 시나리오는 skip.

- [ ] **Step 3: 실패 시 원인 분석 후 수정, 재실행**

원인 전형:
- fixture `e2e_session` 가 `filesystem_root_dir` 디렉토리 부재 → `conftest.py` 에 `tmp_path_factory` 기반 sandbox 생성 + settings 오버라이드.
- TurnStatus 전이가 예상과 다르면 Task 4 에서 놓친 `processor.py` 경로 추가 확인.

- [ ] **Step 4: 커밋**

```bash
git add tests/e2e/test_hitl_e2e.py tests/e2e/conftest.py
git commit -m "test(e2e): rewrite HITL matrix for built-in middleware shape"
```

---

## Task 6: Dead Code & Config Cleanup

**Goal:** 교체로 고아가 된 코드·설정·테스트 전부 정리.

**Files:**
- Delete: `src/services/agent_service/middleware/hitl_middleware.py`
- Delete: `src/services/agent_service/middleware/tool_gate_middleware.py`
- Delete: `src/services/agent_service/tools/registry.py`
- Delete: `src/services/agent_service/tools/builtin/shell_tools.py`
- Delete: `src/services/agent_service/tools/builtin/search_tools.py`
- Delete: `tests/unit/test_hitl_middleware.py`
- Delete: `tests/services/agent_service/middleware/test_tool_gate_middleware.py`
- Delete: `tests/services/agent_service/tools/test_registry.py`
- Modify: `src/services/agent_service/middleware/__init__.py` (exports 정리)
- Modify: `src/configs/agent/openai_chat_agent.py` (`ToolConfig` / `BuiltinToolConfig` 제거)
- Modify: `src/configs/settings.py` — `agent.filesystem_root_dir: str` 추가 (아직 없다면)
- Modify: `yaml_files/services.yml` (tool_config 블록 교체)
- Modify: `yaml_files/services.docker.yml`
- Modify: `yaml_files/services.e2e.yml`

- [ ] **Step 1: 고아 파일 삭제**

```bash
rm src/services/agent_service/middleware/hitl_middleware.py
rm src/services/agent_service/middleware/tool_gate_middleware.py
rm src/services/agent_service/tools/registry.py
rm src/services/agent_service/tools/builtin/shell_tools.py
rm src/services/agent_service/tools/builtin/search_tools.py
rm tests/unit/test_hitl_middleware.py
rm tests/services/agent_service/middleware/test_tool_gate_middleware.py
rm tests/services/agent_service/tools/test_registry.py
```

- [ ] **Step 2: middleware `__init__.py` exports 정리**

Overwrite `src/services/agent_service/middleware/__init__.py`:

```python
from src.services.agent_service.middleware.delegate_middleware import (
    DelegateToolMiddleware,
)

__all__ = ["DelegateToolMiddleware"]
```

- [ ] **Step 3: `configs/agent/openai_chat_agent.py` 정리**

`ToolConfig` / `BuiltinToolConfig` / `FilesystemToolConfig` / `ShellToolConfig` / `WebSearchToolConfig` 등 tool 관련 Pydantic 모델 전체 삭제. `OpenAIChatAgentConfig` 에서 `tool_config: ToolConfig | None` 필드 삭제.

- [ ] **Step 4: `configs/settings.py` `filesystem_root_dir` 추가**

`agent` 섹션 (AgentSettings Pydantic 모델) 에 필드 추가:
```python
class AgentSettings(BaseModel):
    # ... 기존 필드 ...
    filesystem_root_dir: str = "/tmp/agent-workspace"
```

- [ ] **Step 5: YAML 3파일 갱신**

각 `yaml_files/services*.yml` 에서:
- `tool_config:` 블록 (services.yml 51-60, services.docker.yml 52~, services.e2e.yml 52~) 전체 삭제.
- `agent` 또는 `llm_config` 섹션 내 (환경마다 다름) `filesystem_root_dir` 키 추가:
```yaml
# services.yml
agent:
  filesystem_root_dir: "/tmp/agent-workspace"

# services.docker.yml
agent:
  filesystem_root_dir: "/data/agent-workspace"

# services.e2e.yml
agent:
  filesystem_root_dir: "/tmp/agent-workspace-e2e"
```

- [ ] **Step 6: Lint + 기존 테스트 재실행**

```bash
make lint
uv run pytest tests/ -x --ignore=tests/e2e --ignore=tests/spike
```
Expected: 고아 import 없음, 전체 PASS (e2e/spike 제외).

- [ ] **Step 7: 전체 E2E 재실행 (최종 확인)**

Run: `bash scripts/e2e.sh`
Expected: PASS (Task 5 와 동일 결과).

- [ ] **Step 8: 커밋**

```bash
git add -u src/services/agent_service/middleware/ \
           src/services/agent_service/tools/ \
           src/configs/ \
           yaml_files/ \
           tests/
git commit -m "refactor: remove HitL/ToolGate/ToolRegistry dead code and tool_config YAML block"
```

---

## Task 7: Documentation Update

**Goal:** 데이터 흐름 문서를 신 shape 에 맞춰 재작성, 알려진 제약을 KNOWN_ISSUES 에 이월, 구 TODO 문서 삭제.

**Files:**
- Rewrite: `docs/data_flow/agent/HITL_GATE_FLOW.md`
- Modify: `docs/known_issues/KNOWN_ISSUES.md` (entry 추가)
- Delete: `docs/todo/human-in-the-loop.md`

- [ ] **Step 1: `HITL_GATE_FLOW.md` 재작성**

새 내용은 다음을 반영 — 빌트인 미들웨어 사용, payload shape 변경, `request_id` 제거, approve/edit/reject 3-way, `pending_action_count` 기반 검증, `processor.py` reject 경로. 200줄 rule 준수 (`docs/CLAUDE.md`).

핵심 섹션:
- `## 1. Synopsis` — "빌트인 `HumanInTheLoopMiddleware` 로 dangerous tool 을 가로채 FE 승인/편집/거부 받고 재개하는 흐름".
- `## 2. Core Logic` — dangerous 집합(`_build_interrupt_on` 로직), interrupt payload shape, resume shape, turn 상태 전이.
- `## 3. Usage` — FE hitl_request / hitl_response JSON 예제 (list-based).
- `Appendix A 제약` — "한 세션 동시 다중 interrupt 미지원", "연결 끊김 중 suspend 상태 잔존".
- `Appendix B PatchNote` — `2026-04-18: 빌트인 미들웨어 migration 으로 payload shape 전면 교체`.

- [ ] **Step 2: `KNOWN_ISSUES.md` 엔트리 추가**

`docs/known_issues/KNOWN_ISSUES.md` 끝(또는 관련 섹션)에 추가:

```markdown
## HITL resume on FE disconnect

**Severity:** low
**Component:** websocket / agent
**발견:** 2026-04-18 (HITL 빌트인 migration)

FE 가 `hitl_request` 수신 후 응답 없이 연결이 끊기면 LangGraph 그래프가
Mongo checkpoint 에 suspended 상태로 잔존한다. 재연결 시 자동 resume 안 됨
— 사용자가 새 `chat_message` 를 보내면 구 checkpoint 는 버려짐.

TTL 기반 자동 cleanup 또는 reconnect 시 pending HITL 복원 UX 는 후속 이슈.
```

- [ ] **Step 3: 구 TODO 문서 삭제**

```bash
rm docs/todo/human-in-the-loop.md
```

- [ ] **Step 4: 문서 커밋**

```bash
git add docs/data_flow/agent/HITL_GATE_FLOW.md \
        docs/known_issues/KNOWN_ISSUES.md
git add -u docs/todo/human-in-the-loop.md  # deletion
git commit -m "docs: update HITL flow + KNOWN_ISSUES for built-in middleware"
```

- [ ] **Step 5: PR 생성**

```bash
git push -u origin refactor/hitl
gh pr create --base develop --title "feat: migrate HITL to built-in middleware and enable filesystem tools" --body "$(cat <<'EOF'
## Summary
- 커스텀 `HitLMiddleware` / `ToolGateMiddleware` / `ToolRegistry` 를 LangChain 빌트인 `HumanInTheLoopMiddleware` + `FileManagementToolkit` + 신규 `EditFileTool` 로 교체.
- WebSocket HITL 페이로드를 빌트인 list-based shape 로 재설계 (approve/edit/reject 3-way).
- 기존 YAML 토글로 비활성화돼 있던 filesystem tools 를 상시 로드 + HITL 게이트 적용 — 단순 refactor 가 아닌 기능 확장 포함.

Spec: `docs/superpowers/specs/2026-04-18-hitl-builtin-middleware-migration-design.md`
Plan: `docs/superpowers/plans/2026-04-18-hitl-builtin-middleware-migration.md`

## Test plan
- [x] Task 1 spike: MongoDB checkpointer + HITL 호환
- [x] Unit tests (filesystem, agent stream, event handling, WS models)
- [x] E2E full matrix — `bash scripts/e2e.sh`
- [x] `make lint`
EOF
)"
```

---

## Self-Review Checklist (작성자용 — 플랜 커밋 전 확인)

**Spec coverage:**
- §2 스코프 델타 → Task 3 (filesystem_tools 재작성), Task 4 (agent+WS swap), Task 6 (dead code/config), Task 7 (docs) 전부 커버.
- §3 Tool Layer → Task 3.
- §4 HITL Middleware 설정 → Task 4 Step 4 (`_build_interrupt_on` + chain).
- §5 WebSocket 프로토콜 → Task 2 (models) + Task 4 Steps 5·6·7 (handlers·event_handlers·processor).
- §6 에러 처리 → Task 4 Step 6 (`decisions count mismatch`), Task 7 Step 2 (disconnect KNOWN_ISSUES).
- §7 테스트 전략 → Task 1 (spike), Task 2~4 (unit), Task 5 (E2E).
- §8 마이그레이션 순서 → Task 1~7 1:1 매핑.
- §9 비스코프/위험 → Task 7 Step 2 (disconnect), PR body (locale 회귀).

**Placeholder scan:** TBD / TODO 없음 (확인).

**Type consistency:**
- `decisions: list[dict]` — Task 4 Step 4 (resume_after_approval 시그니처) / Step 6 (handlers.py 호출) / Step 7 (processor.py 호출) 동일.
- `pending_action_count` — Task 4 Step 5 (event_handlers 에서 write) / Step 6 (handlers 에서 read) 동일 키.
- `_build_interrupt_on` 시그니처 `set[str] -> dict[str, bool]` — Task 4 Step 1 테스트 / Step 4 구현 동일.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-18-hitl-builtin-middleware-migration.md`.

**두 실행 옵션:**

**1. Subagent-Driven (권장)** — 태스크마다 fresh subagent dispatch, 태스크 간 리뷰, 빠른 반복.

**2. Inline Execution** — 현재 세션에서 `executing-plans` 로 배치 실행, 체크포인트마다 리뷰.

어느 방식으로 진행할까요?
