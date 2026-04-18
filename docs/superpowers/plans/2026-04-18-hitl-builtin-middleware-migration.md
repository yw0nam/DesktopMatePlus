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

Pattern mirrors tests/spike/test_interrupt_in_middleware.py — uses
FakeToolChatModel so no live LLM is needed; MONGO_URL env var required.
"""

import os
from collections.abc import Callable, Sequence
from typing import Any
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.language_models.chat_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import Command
from pymongo import MongoClient


MONGO_URL = os.getenv("MONGO_URL", "mongodb://admin:test@192.168.0.43:27017/")


class FakeToolChatModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel that supports bind_tools (returns self)."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        return self


@tool
def mutating_tool(payload: str) -> str:
    """Fake mutating tool that must be gated by HITL."""
    return f"applied: {payload}"


def _fake_llm() -> FakeToolChatModel:
    return FakeToolChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{
                    "name": "mutating_tool",
                    "args": {"payload": "x"},
                    "id": "call_1",
                    "type": "tool_call",
                }],
            ),
            AIMessage(content="Done."),
        ]
    )


@pytest.mark.spike
@pytest.mark.asyncio
async def test_mongodb_saver_supports_hitl_interrupt_and_resume():
    """Agent with MongoDBSaver pauses on mutating_tool, resumes on approve."""
    if not MONGO_URL:
        pytest.skip("MONGO_URL env var not set")

    mongo_client = MongoClient(MONGO_URL)
    # Use a unique db name per test to avoid cross-run contamination
    checkpointer = MongoDBSaver(client=mongo_client, db_name=f"spike_{uuid4().hex[:8]}")

    agent = create_agent(
        model=_fake_llm(),
        tools=[mutating_tool],
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={"mutating_tool": True}),
        ],
    )

    thread_id = f"spike-{uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # Drain astream to reach interrupt
    interrupt_value = None
    async for stream_type, data in agent.astream(
        {"messages": [("human", "call mutating_tool")]},
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates" and "__interrupt__" in data:
            interrupt_value = data["__interrupt__"][0].value

    assert interrupt_value is not None, "Graph did not reach interrupt"
    assert interrupt_value["action_requests"][0]["name"] == "mutating_tool"

    # Resume with approve — MongoDB checkpoint must be readable on same thread_id
    tool_executed = False
    async for stream_type, data in agent.astream(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
        stream_mode=["updates"],
    ):
        if stream_type == "updates":
            for node_name, updates in data.items():
                if node_name == "tools":
                    for msg in updates.get("messages", []):
                        if "applied: x" in str(getattr(msg, "content", "")):
                            tool_executed = True

    assert tool_executed, "Tool did not execute after approve resume"
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

# Replace MongoClient/MongoDBSaver creation inside the test with:
mongo_client = AsyncIOMotorClient(MONGO_URL)
checkpointer = AsyncMongoDBSaver(client=mongo_client, db_name=f"spike_{uuid4().hex[:8]}")
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

① 파일 상단 import 교체 — `HitLMiddleware`(현 줄 22) + `ToolGateMiddleware`(현 줄 23-25, 멀티라인) 총 4줄 삭제. `DelegateToolMiddleware` import (줄 19-21) 유지. 추가:
```python
from langchain.agents.middleware import HumanInTheLoopMiddleware
```

② 파일 상단(클래스 밖, personas 로더 위)에 상수·helper 추가:
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

③ `OpenAIChatAgent.__init__` 시그니처(현 줄 56-75) 교체 — `tool_config: dict | None = None` 파라미터를 `filesystem_root_dir: str = "/tmp/agent-workspace"` 로 바꾸고, `self.tool_config = tool_config` 라인을 `self.filesystem_root_dir = filesystem_root_dir` 로:
```python
def __init__(
    self,
    temperature: float,
    top_p: float,
    openai_api_key: str | None = None,
    openai_api_base: str | None = None,
    model_name: str | None = None,
    filesystem_root_dir: str = "/tmp/agent-workspace",
    **kwargs,
):
    self.temperature = temperature
    self.top_p = top_p
    self.openai_api_key = openai_api_key
    self.openai_api_base = openai_api_base
    self.model_name = model_name
    self.filesystem_root_dir = filesystem_root_dir
    self.agent = None
    self._mcp_tools: list = []
    self._personas: dict[str, str] = {}
    super().__init__(**kwargs)
    logger.info(f"Agent initialized: model={self.model_name}")
```

④ `OpenAIChatAgentConfig` (`src/configs/agent/openai_chat_agent.py:50-79`) 에 `filesystem_root_dir: str` 필드 추가 (기존 `tool_config` 필드는 **Task 6에서** 제거; 여기서는 둘 다 존재해도 `__init__`에서 tool_config 를 받지 않으므로 ignored). 추가 위치 (파일 끝 `tool_config` 필드 앞):
```python
filesystem_root_dir: str = Field(
    default="/tmp/agent-workspace",
    description="Sandbox root for filesystem tools (ReadFile/WriteFile/EditFile/etc).",
)
```

⑤ `initialize_async` 내부 미들웨어·툴 구성 블록(현재 줄 139-182) 교체:
```python
from src.services.agent_service.tools.builtin.filesystem_tools import (
    get_filesystem_tools,
)

custom_tools = list(self._mcp_tools)
profile_svc = get_user_profile_service()
if profile_svc is not None:
    custom_tools.append(UpdateUserProfileTool(service=profile_svc))

custom_tools.extend(get_filesystem_tools(root_dir=self.filesystem_root_dir))

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

⑥ YAML 3개 파일에 `llm_config.configs.filesystem_root_dir` 추가 — `services.yml`/`services.docker.yml`/`services.e2e.yml` 각 `llm_config.configs` 블록 끝에 한 줄씩 (환경별 경로):
```yaml
# services.yml
llm_config:
  configs:
    # ... 기존 필드 유지 ...
    filesystem_root_dir: "/tmp/agent-workspace"

# services.docker.yml
    filesystem_root_dir: "/data/agent-workspace"

# services.e2e.yml
    filesystem_root_dir: "/tmp/agent-workspace-e2e"
```

⑦ **Task 1 Step 3 폴백(AsyncMongoDBSaver)이 선택된 경우에만**: `openai_chat_agent.py:127-137` 의 `MongoDBSaver` 초기화 블록도 아래로 교체 (현행 `mongo_client` 는 동기이므로 motor client 로 전환 필요):
```python
if mongo_client:
    try:
        from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
        from motor.motor_asyncio import AsyncIOMotorClient

        async_client = AsyncIOMotorClient(mongo_client.address[0] and str(mongo_client.address))
        # 또는 service_manager 에서 AsyncIOMotorClient 싱글톤을 따로 만들어 주입
        checkpointer = AsyncMongoDBSaver(client=async_client)
    except ImportError:
        logger.warning("AsyncMongoDBSaver not available, checkpointer disabled")
```
Task 1 Step 2 에서 sync saver 로 PASS 라면 이 단계 **스킵**.

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
        src/configs/agent/openai_chat_agent.py \
        src/services/websocket_service/manager/handlers.py \
        src/services/websocket_service/message_processor/processor.py \
        src/services/websocket_service/message_processor/event_handlers.py \
        yaml_files/services.yml \
        yaml_files/services.docker.yml \
        yaml_files/services.e2e.yml \
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

파일 전체 구조 — 기존 `tests/e2e/test_hitl_e2e.py` 의 helpers(`_connect_and_authorize`, `_collect_until_terminal`, `_recv_skip_ping`, `_send_chat`)는 **그대로 보존**. 테스트 클래스만 교체. 아래 9개 테스트 각 scenario를 `TestHitLBuiltinFlow` 클래스에 넣는다. `e2e_session` fixture 는 dict (`{"base_url", "ws_url"}`) — 현행 `tests/e2e/conftest.py:22-30` 참조.

상단에 추가 imports:
```python
from pathlib import Path
import yaml

def _filesystem_root_from_yaml() -> Path:
    # services.e2e.yml 의 llm_config.configs.filesystem_root_dir 을 읽어옴
    cfg = yaml.safe_load(Path("yaml_files/services.e2e.yml").read_text())
    return Path(cfg["llm_config"]["configs"]["filesystem_root_dir"])
```

**시나리오 1 — normal chat:**
```python
@pytest.mark.e2e
class TestHitLBuiltinFlow:
    async def test_normal_chat_no_hitl_request(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_CHAT_PROMPT))
            events = await _collect_until_terminal(ws)
            assert "hitl_request" not in [e["type"] for e in events]
            assert any(e["type"] == "stream_end" for e in events)
        finally:
            await ws.close()
```

**시나리오 2 — safe tool no HITL:**
```python
    async def test_safe_tool_no_hitl_request(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            await ws.send(_send_chat(SAFE_TOOL_PROMPT))
            events = await _collect_until_terminal(ws)
            if "hitl_request" in [e["type"] for e in events]:
                pytest.skip("LLM chose an MCP/dangerous tool instead of search_memory")
            assert any(e["type"] == "stream_end" for e in events)
        finally:
            await ws.close()
```

**시나리오 3 — write_file approve:**
```python
    async def test_write_file_approve(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'hello-e2e' to a file named e2e_approve.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")
            assert len(hitl["action_requests"]) == 1
            assert hitl["action_requests"][0]["name"] == "write_file"

            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [{"type": "approve"}],
            }))
            final = await _collect_until_terminal(ws, terminal_types={"stream_end", "error"})
            assert any(e["type"] == "stream_end" for e in final)

            sandbox = _filesystem_root_from_yaml() / "e2e_approve.txt"
            assert sandbox.exists()
            assert "hello-e2e" in sandbox.read_text()
            sandbox.unlink(missing_ok=True)
        finally:
            await ws.close()
```

**시나리오 4 — reject with message:**
```python
    async def test_write_file_reject_with_message(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'x' to reject_e2e.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")

            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [{"type": "reject", "message": "path is unsafe"}],
            }))
            final = await _collect_until_terminal(ws, terminal_types={"stream_end", "error"})
            # Agent handles rejection with alternate response — LLM-dependent
            if not any(e["type"] == "stream_end" for e in final):
                pytest.skip("LLM did not produce stream_end after rejection (nondeterministic)")

            sandbox = _filesystem_root_from_yaml() / "reject_e2e.txt"
            assert not sandbox.exists()
        finally:
            await ws.close()
```

**시나리오 5 — edit decision:**
```python
    async def test_write_file_edit(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'yuri' to wrong_name.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")

            edited_args = dict(hitl["action_requests"][0]["arguments"])
            edited_args["file_path"] = "edited_name.txt"
            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [{
                    "type": "edit",
                    "edited_action": {"name": "write_file", "args": edited_args},
                }],
            }))
            final = await _collect_until_terminal(ws, terminal_types={"stream_end", "error"})
            assert any(e["type"] == "stream_end" for e in final)

            root = _filesystem_root_from_yaml()
            assert (root / "edited_name.txt").exists()
            assert not (root / "wrong_name.txt").exists()
            (root / "edited_name.txt").unlink(missing_ok=True)
        finally:
            await ws.close()
```

**시나리오 6 — multi parallel tool calls:**
```python
    async def test_multi_parallel_tool_calls(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = (
                "In one turn, call write_file to create multi1.txt='a' AND "
                "write_file to create multi2.txt='b'. Both calls in a single response."
            )
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None or len(hitl["action_requests"]) != 2:
                pytest.skip("LLM did not emit 2 parallel tool calls")

            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [{"type": "approve"}, {"type": "reject", "message": "skip second"}],
            }))
            final = await _collect_until_terminal(ws, terminal_types={"stream_end", "error"})
            assert any(e["type"] == "stream_end" for e in final)

            root = _filesystem_root_from_yaml()
            assert (root / "multi1.txt").exists()
            assert not (root / "multi2.txt").exists()
            (root / "multi1.txt").unlink(missing_ok=True)
        finally:
            await ws.close()
```

**시나리오 7 — decisions count mismatch:**
```python
    async def test_decisions_count_mismatch_returns_error(self, e2e_session):
        ws = await _connect_and_authorize(e2e_session["ws_url"])
        try:
            prompt = "Please write 'x' to mismatch_e2e.txt using write_file."
            await ws.send(_send_chat(prompt))
            events = await _collect_until_terminal(ws)
            hitl = next((e for e in events if e["type"] == "hitl_request"), None)
            if hitl is None:
                pytest.skip("LLM did not choose write_file")
            assert len(hitl["action_requests"]) == 1

            # Send 0 decisions — mismatch
            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [],
            }))
            err = await _recv_skip_ping(ws, timeout=15.0)
            assert err["type"] == "error"
            assert err.get("code") == 4004

            # Retry with correct count
            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [{"type": "reject"}],
            }))
            final = await _collect_until_terminal(ws, terminal_types={"stream_end", "error"})
            assert any(e["type"] == "stream_end" for e in final)

            (_filesystem_root_from_yaml() / "mismatch_e2e.txt").unlink(missing_ok=True)
        finally:
            await ws.close()
```

**시나리오 8 & 9 — 기존 `TestHitLProtocol` 클래스 유지**:
`test_hitl_response_without_pending_approval` / `test_hitl_response_requires_authentication` 은 현행 테스트(`tests/e2e/test_hitl_e2e.py:133-187`)를 거의 그대로 유지하되, payload 의 `request_id`/`approved` 필드를 `decisions` 로 바꾼다:
```python
            await ws.send(json.dumps({
                "type": "hitl_response",
                "decisions": [{"type": "approve"}],
            }))
```
검증 로직 (error 응답 / auth 에러) 은 동일.

**cleanup fixture**: 테스트 모듈 상단에 autouse fixture 추가해 filesystem_root 하위 e2e_*.txt / multi*.txt / *_e2e.txt 를 module teardown 에 청소:
```python
@pytest.fixture(autouse=True, scope="module")
def _cleanup_e2e_files():
    yield
    root = _filesystem_root_from_yaml()
    if root.exists():
        for name in ("e2e_approve.txt", "reject_e2e.txt", "edited_name.txt",
                     "wrong_name.txt", "multi1.txt", "multi2.txt", "mismatch_e2e.txt"):
            (root / name).unlink(missing_ok=True)
```

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
- Modify: `src/configs/agent/openai_chat_agent.py` (`ToolConfig`/`BuiltinToolConfig`/`FilesystemToolConfig`/`ShellToolConfig`/`WebSearchToolConfig` 및 `tool_config` 필드 제거 — `filesystem_root_dir` 필드는 Task 4 Step 4 ④ 에서 이미 추가됨)
- Modify: `yaml_files/services.yml` / `services.docker.yml` / `services.e2e.yml` (`tool_config:` 블록만 삭제 — `llm_config.configs.filesystem_root_dir` 는 Task 4 Step 4 ⑥ 에서 이미 추가됨)

**Note:** `src/configs/settings.py` 는 이 마이그레이션에서 **건드리지 않는다**. `filesystem_root_dir` 은 기존 YAML `llm_config.configs.*` 로딩 경로를 통해 `OpenAIChatAgentConfig` → `OpenAIChatAgent.__init__` kwarg 로 직접 전달됨 (다른 `openai_api_base`/`model_name` 필드와 동일 패턴).

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

파일(현행 1-79줄) 을 다음 버전으로 축소 — tool 관련 Pydantic 모델 전부 삭제, `OpenAIChatAgentConfig.tool_config` 필드 삭제. `filesystem_root_dir` 필드는 Task 4 에서 이미 추가된 상태(유지):
```python
"""OpenAI Chat Agent configuration."""

import os

from pydantic import BaseModel, Field


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
    filesystem_root_dir: str = Field(
        default="/tmp/agent-workspace",
        description="Sandbox root for filesystem tools (ReadFile/WriteFile/EditFile/etc).",
    )
```

Also remove `model_validator` from imports if unused after removal.

- [ ] **Step 4: YAML 3파일 — `tool_config:` 블록만 삭제**

각 `yaml_files/services*.yml` 에서 `tool_config:` 블록 (services.yml 51-60 확인; 나머지 두 파일은 `grep -n 'tool_config:'` 로 라인 확인 후 해당 블록 전체 삭제).

**`filesystem_root_dir` 는 이미 Task 4 Step 4 ⑥ 에서 `llm_config.configs:` 하위에 추가되어 있음** — 중복 추가 금지.

- [ ] **Step 5: Lint + 기존 테스트 재실행**

```bash
make lint
uv run pytest tests/ -x --ignore=tests/e2e --ignore=tests/spike
```
Expected: 고아 import 없음, 전체 PASS (e2e/spike 제외).

- [ ] **Step 6: 전체 E2E 재실행 (최종 확인)**

Run: `bash scripts/e2e.sh`
Expected: PASS (Task 5 와 동일 결과).

- [ ] **Step 7: 커밋**

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

## Breaking changes (FE 주의)
- WS 메시지 `hitl_request` payload 변경: `tool_name` / `tool_args` / `request_id` 제거 → `action_requests` / `review_configs` 리스트로 교체.
- WS 메시지 `hitl_response` payload 변경: `request_id` / `approved` 제거 → `decisions` 리스트 (approve/edit/reject + optional edited_action / message).
- Reject 시 ToolMessage 기본 문구가 빌트인의 영문 default 로 전환됨. FE 가 `decisions[i].message` 에 한국어 이유를 보내지 않으면 유리의 응답 맥락이 영문 텍스트를 참조할 수 있음 — FE 에서 기본 reject 사유 한국어 제공 권장.

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
- §2 스코프 델타 → Task 3 (filesystem_tools), Task 4 (agent+config+YAML+WS swap), Task 6 (dead code/config), Task 7 (docs) 전부 커버.
- §3 Tool Layer → Task 3.
- §4 HITL Middleware 설정 → Task 4 Step 4 ②·⑤ (`_build_interrupt_on` + chain).
- §5 WebSocket 프로토콜 → Task 2 (models) + Task 4 Steps 5·6·7 (event_handlers·handlers·processor).
- §6 에러 처리 → Task 4 Step 6 (`decisions count mismatch`), Task 7 Step 2 (disconnect KNOWN_ISSUES). Locale 회귀는 PR body Breaking changes 섹션.
- §7 테스트 전략 → Task 1 (spike), Task 2~4 (unit), Task 5 (E2E).
- §8 마이그레이션 순서 → Task 1~7 1:1 매핑.
- §9 비스코프/위험 → Task 7 Step 2 (disconnect), PR body (locale 회귀, breaking changes).

**Placeholder scan:** TBD / TODO 없음 (확인).

**Type consistency:**
- `decisions: list[dict]` — Task 4 Step 4 ⑤ (resume_after_approval 시그니처) / Step 6 (handlers.py 호출) / Step 7 (processor.py 호출) 동일.
- `pending_action_count` — Task 4 Step 5 (event_handlers 에서 write) / Step 6 (handlers 에서 read) / Step 7 (processor 에서 read) 동일 키.
- `_build_interrupt_on` 시그니처 `set[str] -> dict[str, bool]` — Task 4 Step 1 테스트 / Step 4 ② 구현 동일.
- `filesystem_root_dir` — `OpenAIChatAgentConfig` 필드 (Task 4 Step 4 ④) / `OpenAIChatAgent.__init__` kwarg (Task 4 Step 4 ③) / YAML `llm_config.configs.filesystem_root_dir` (Task 4 Step 4 ⑥) / `self.filesystem_root_dir` 사용 (Task 4 Step 4 ⑤) 동일 키.

**Ordering:**
- Task 4 내부 Step 4 가 config 필드 추가 + YAML 추가를 포함 — Task 6 에서 오래된 `tool_config` 필드·YAML 블록을 제거할 때 `filesystem_root_dir` 은 이미 로드 가능한 상태.
- Task 1 Step 3 (AsyncMongoDBSaver 폴백) 선택 시 Task 4 Step 4 ⑦ 이 호출됨 — 조건부 경로 명시.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-18-hitl-builtin-middleware-migration.md`.

**두 실행 옵션:**

**1. Subagent-Driven (권장)** — 태스크마다 fresh subagent dispatch, 태스크 간 리뷰, 빠른 반복.

**2. Inline Execution** — 현재 세션에서 `executing-plans` 로 배치 실행, 체크포인트마다 리뷰.

어느 방식으로 진행할까요?
