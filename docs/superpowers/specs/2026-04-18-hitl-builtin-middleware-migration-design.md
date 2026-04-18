# HITL Built-in Middleware Migration Design

**Date:** 2026-04-18
**Scope:** 커스텀 `HitLMiddleware` / `ToolGateMiddleware` / `ToolRegistry` 삭제 → LangChain 빌트인 `HumanInTheLoopMiddleware` + `FileManagementToolkit` + 신규 `EditFileTool`로 교체
**Approach:** Big-bang 단일 PR (commit 8개로 TDD 사이클 분리)
**Status:** Ready for `writing-plans`

## 1. 목표

- 빌트인 `HumanInTheLoopMiddleware` 채택 — approve/edit/reject 3-way + list-based 멀티콜 지원.
- `FileManagementToolkit(root_dir=...)` 7툴 + 신규 `EditFileTool` → 실제 디스크 쓰기 유지.
- 커스텀 HITL·ToolGate·ToolRegistry·빌트인 툴 래퍼 전면 삭제. YAML `tool_config.*` 토글 제거, 단일 `filesystem_root_dir` 키로 축소.
- FE 미작업 상태 활용: WS 페이로드를 빌트인 shape 1:1로 재설계.
- Shell tool은 본 스코프 제외 (빌트인 `ShellToolMiddleware`가 현재 HITL과 비호환 — 추후 별도 이슈).

## 2. 스코프 델타

| 분류 | 파일 | 액션 |
|---|---|---|
| 삭제 | `middleware/hitl_middleware.py` | 빌트인 교체 |
| 삭제 | `middleware/tool_gate_middleware.py` | shell 보류 + FS는 `root_dir` 샌드박스로 충분 |
| 삭제 | `tools/registry.py` | 하드코딩 전환 |
| 삭제 | `tools/builtin/shell_tools.py` | shell 보류 |
| 삭제 | `tools/builtin/search_tools.py` | MCP로 이관 예정 |
| 재작성 | `tools/builtin/filesystem_tools.py` | `FileManagementToolkit` + 같은 파일에 `EditFileTool` 배치 |
| 수정 | `services/agent_service/openai_chat_agent.py` | 미들웨어 체인 교체, `__interrupt__` 파서·`resume_after_approval()` 재작성 |
| 수정 | `configs/agent/openai_chat_agent.py` | `ToolConfig`/`BuiltinToolConfig` 제거, `filesystem_root_dir: str` 단일 키 추가 |
| 수정 | `yaml_files/services*.yml` | `tool_config:` 블록 제거 → `agent_service.filesystem_root_dir` |
| 교체 | `models/websocket.py` | `HitLRequestMessage`/`HitLResponseMessage` list-based shape |
| 수정 | `websocket_service/manager/handlers.py` | `handle_hitl_response()` 신 shape |
| 수정 | `websocket_service/message_processor/event_handlers.py` | hitl_request payload 필드 변경 |
| 재작성 | `tests/unit/test_hitl_*.py`, `tests/e2e/test_hitl_e2e.py` | 신 스키마 기반 전면 재작성 |
| 신규 | `tests/unit/test_edit_file_tool.py` | EditFileTool 단위 테스트 |
| 신규 | `tests/integration/test_hitl_mongodb_checkpointer.py` | `AsyncMongoDBSaver` + HITL 호환 스파이크 |
| 수정 | `docs/data_flow/agent/HITL_GATE_FLOW.md` | payload 섹션 갱신 |

유지: `AsyncMongoDBSaver`, `DelegateToolMiddleware` + `delegate_task`, LTM/Profile/Summary/TaskStatus hook 미들웨어, MCP 로딩, 메모리 툴(별도 이슈).

## 3. Tool Layer 설계

`tools/builtin/filesystem_tools.py` 재작성: `FileManagementToolkit` 7툴 + 신규 `EditFileTool`.

```python
import asyncio
from pathlib import Path

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field


def get_filesystem_tools(root_dir: str) -> list[BaseTool]:
    """FileManagementToolkit (7 tools) + EditFileTool, all sandboxed to root_dir."""
    toolkit_tools = FileManagementToolkit(root_dir=root_dir).get_tools()
    return [*toolkit_tools, EditFileTool(root_dir=root_dir)]


class _EditFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path within root_dir")
    old_string: str = Field(..., description="Exact substring to replace (must occur exactly once)")
    new_string: str = Field(..., description="Replacement string")


class EditFileTool(BaseTool):
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

Agent 합성 (`openai_chat_agent.py::initialize_async`):

```python
custom_tools = list(self._mcp_tools)
if profile_svc:
    custom_tools.append(UpdateUserProfileTool(service=profile_svc))
custom_tools.extend(get_filesystem_tools(root_dir=self.filesystem_root_dir))
# DelegateToolMiddleware 가 delegate_task 를 per-call 주입 — custom_tools 에 추가 X
```

## 4. HITL 미들웨어 설정

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
]
```

순서 근거: HITL(`after_model` 타이밍)이 tool call 을 먼저 게이트 → 승인 시 제어흐름이 `awrap_tool_call` 체인으로 내려가며 `DelegateToolMiddleware`가 `delegate_task` 인스턴스를 주입. `before_model` hook 들은 system prompt 주입만 하므로 HITL 과 orthogonal.

매트릭스 외 툴(`read_file`, `list_directory`, `file_search`, profile/memory 빌트인)은 자동 실행.

## 5. WebSocket 프로토콜

### Server → Client: `hitl_request`

```python
class HitLActionRequest(BaseModel):
    name: str
    arguments: dict[str, Any]
    description: str


class HitLReviewConfig(BaseModel):
    action_name: str
    allowed_decisions: list[Literal["approve", "edit", "reject"]]


class HitLRequestMessage(BaseMessage):
    type: MessageType = MessageType.HITL_REQUEST
    session_id: str
    action_requests: list[HitLActionRequest]
    review_configs: list[HitLReviewConfig]  # action_requests 와 1:1, 같은 순서
```

### Client → Server: `hitl_response`

```python
class HitLEditedAction(BaseModel):
    name: str
    args: dict[str, Any]


class HitLDecision(BaseModel):
    type: Literal["approve", "edit", "reject"]
    edited_action: HitLEditedAction | None = None   # type="edit" 때만
    message: str | None = None                       # type="reject" 시 선택

    @model_validator(mode="after")
    def _check_payload(self) -> "HitLDecision":
        if self.type == "edit" and self.edited_action is None:
            raise ValueError("edit decision requires edited_action")
        if self.type == "approve" and (self.edited_action or self.message):
            raise ValueError("approve decision must not carry edited_action or message")
        return self


class HitLResponseMessage(BaseMessage):
    type: MessageType = MessageType.HITL_RESPONSE
    decisions: list[HitLDecision]  # action_requests 와 같은 순서·길이
```

### 주요 변경점

| 항목 | Before | After |
|---|---|---|
| `request_id` 필드 | 있음 | 삭제 (thread_id=session_id 로 correlation) |
| 단일 vs 리스트 | 1 request | list (병렬 tool call 지원) |
| 결정 종류 | approve/reject 2가지 | approve/edit/reject 3가지 |
| 필드명 | `tool_name`/`tool_args` | `name`/`arguments` (빌트인 shape) |

### 서버 플로우 diff

`_consume_astream` 의 `__interrupt__` 파서: 리스트 그대로 전달.

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

`resume_after_approval()` 재작성:

```python
async def resume_after_approval(
    self, session_id: str, decisions: list[dict], *, context: dict | None = None,
):
    from langgraph.types import Command
    config = {"configurable": {"thread_id": session_id}}
    astream_iter = self.agent.astream(
        Command(resume={"decisions": decisions}),
        config=config, context=context, stream_mode=["messages", "updates"],
    )
    async for event in self._consume_astream(astream_iter, session_id):
        yield event
```

`handlers.py::handle_hitl_response`: `HitLResponseMessage.decisions` 를 dict 리스트로 변환해 agent 로 전달. 기존 `TurnStatus.AWAITING_APPROVAL` 가드 유지.

`event_handlers.py`: hitl_request 이벤트에 `action_requests`/`review_configs` 필드를 실어 WS 로 포워드.

## 6. 에러 처리 & 엣지 케이스

- **Reject 처리**: 빌트인에 위임. `ToolMessage(content=decision.message or default)` 가 state 에 삽입되고 모델 재호출. 커스텀 "사용자가 거부했습니다" 문자열 삭제.
- **Decisions 길이 불일치**: `handle_hitl_response` 에서 서버측 보유 action_requests 개수와 비교. 불일치 시 `ErrorMessage(code=4004, error="decisions count mismatch")` 응답, graph 상태 유지 → 클라이언트 재전송 가능.
- **Stale / AWAITING_APPROVAL 아님**: 기존 가드 유지 (`ErrorMessage(code=4004)`).
- **Turn 상태 전이**: `PROCESSING → AWAITING_APPROVAL → PROCESSING → stream_end`. 프로토콜 오류 시 AWAITING_APPROVAL 유지.
- **Edit 결정 유효성**: 서버 사전검증 없음 (YAGNI). 엉뚱한 args 면 tool 자체 validation error → ToolMessage → 모델 재시도.
- **연결 끊김 중 interrupt**: Mongo checkpoint 에 suspended 상태 잔존 — 현행 제약 이월. `KNOWN_ISSUES.md` 에 기재.
- **Timeout / partial re-approval / backend force-abandon**: 본 스코프 제외.

## 7. 테스트 전략

### 삭제
- `tests/unit/test_hitl_middleware.py` (커스텀 미들웨어 소멸)
- `tests/unit/test_tool_gate_middleware.py` 및 `test_tool_registry.py` (있다면)

### 재작성
- `tests/unit/test_hitl_models.py` — 신 스키마 + `HitLDecision` validator.
- `tests/unit/test_hitl_agent_stream.py` — `__interrupt__` 파서 (single + multi action_requests).
- `tests/unit/test_hitl_event_handling.py` — event_handlers payload 포워딩.
- `tests/e2e/test_hitl_e2e.py` — 매트릭스 재작성 (아래).

### 신규
- `tests/unit/test_edit_file_tool.py` — unique match, absent/multi match, absolute path, traversal.
- `tests/integration/test_hitl_mongodb_checkpointer.py` — **구현 1단계 블로커**. 실제 Mongo + `AsyncMongoDBSaver` + `HumanInTheLoopMiddleware` 최소 조합으로 interrupt→checkpoint→resume 검증.

### E2E 매트릭스

| # | 시나리오 | 검증 |
|---|---|---|
| 1 | Normal chat | `hitl_request` 없음 |
| 2 | Safe tool (read_file) | `hitl_request` 없음 |
| 3 | write_file + approve | 1건 action_requests → approve → stream_end |
| 4 | write_file + reject(message) | reject → agent 대체 응답 (비결정성: 기존 `pytest.skip` 패턴) |
| 5 | write_file + edit | edited_action 으로 재실행 → stream_end |
| 6 | 병렬 dangerous 2개 + 혼합 결정 | 2건 decisions → 순서 보존 |
| 7 | decisions count 불일치 | ErrorMessage(4004), 상태 유지, 재전송 성공 |
| 8 | AWAITING_APPROVAL 아닐 때 hitl_response | ErrorMessage(4004) |
| 9 | 인증 전 hitl_response | ErrorMessage (현행 유지) |

TDD: (1) checkpointer 스파이크 RED→GREEN → (2) 모델 → (3) 툴 → (4) 미들웨어 → (5) WS 핸들러 → (6) E2E.

## 8. 마이그레이션 순서

| # | 커밋 | 게이트 |
|---|---|---|
| 1 | MongoDB checkpointer 호환 스파이크 (`test_hitl_mongodb_checkpointer.py`, 필요시 `pyproject.toml` bump) | **블로커** |
| 2 | 신 WS HITL 모델 + unit 테스트 | `pytest` GREEN |
| 3 | `filesystem_tools.py` 재작성 + `EditFileTool` + unit 테스트 (shell/search/registry 는 아직 유지) | `pytest` GREEN |
| 4 | `openai_chat_agent.py` 미들웨어 체인 교체 + `__interrupt__` 파서·`resume_after_approval()` + unit 테스트 | unit GREEN |
| 5 | `handlers.py` / `event_handlers.py` 재배선 + unit 테스트 | unit GREEN |
| 6 | E2E 전면 재작성 | `bash scripts/e2e.sh` GREEN (CLAUDE.md 강제) |
| 7 | 데드 코드 정리: `hitl_middleware.py`, `tool_gate_middleware.py`, `registry.py`, `shell_tools.py`, `search_tools.py`, `ToolConfig` 스키마, YAML `tool_config:` 블록 | `make lint` GREEN |
| 8 | 문서 갱신: `HITL_GATE_FLOW.md`, `KNOWN_ISSUES.md`, `docs/todo/human-in-the-loop.md` | — |

PR 메타:
- 타이틀: `refactor: replace custom HITL with LangChain built-in middleware`
- 라벨: `type:refactor`, `component:agent`, `component:websocket`

## 9. 비스코프 & 위험

### 명시적 비스코프
- Shell tool 재도입 (빌트인 `ShellToolMiddleware` 는 HITL 비호환 — 별도 이슈).
- 메모리 툴(`add_memory`/`update_memory`/`delete_memory`/`search_memory`) 폴리싱.
- `delegate_task` UX 재디자인 (예: 자동 승인 + 미리보기).
- Web search tool (MCP 이관 예정).
- HITL timeout / partial retry / disconnect resume 자동화.

### 위험
- **AsyncMongoDBSaver + HITL 호환 미확인**: 공식 예제는 `AsyncPostgresSaver`/`InMemorySaver` 만 등장. Commit #1 에서 검증 필수. 실패 시 재논의.
- **멀티콜 시나리오(#6) 비결정성**: LLM 이 병렬 tool call 을 내는지 제어 불가. 고정 프롬프트로 확률 높이되, 필요 시 `pytest.skip` 패턴.
- **E2E 재작성 범위 큼**: 기존 테스트 9개 중 최소 6개 터치 — 리뷰 부담.

---

## Appendix

### A. 미검증 가정 (구현 단계 확인)

- `HumanInTheLoopMiddleware` 의 `Interrupt.value` shape 이 `action_requests: list[{name, arguments, description}]` + `review_configs: list[{action_name, allowed_decisions}]` 인 것 — 공식 문서 기반, 실제 런타임 검증은 commit #1 스파이크에서.
- `Command(resume={"decisions": [...]})` 형태가 approve/edit/reject 모두 동일한 dispatch 로 동작.
- 빈 `action_requests` 리스트로 interrupt 가 발생하지 않는다 (빌트인 가드 가정 — 방어 코드 추가 안 함).
- `DelegateToolMiddleware.awrap_tool_call` 이 HITL 승인 이후 체인에서 정상 실행.

### B. 참고

- [LangChain Built-in Middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain Human-in-the-Loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangChain Filesystem Tools](https://docs.langchain.com/oss/python/integrations/tools/filesystem)
- 기존 설계: `docs/todo/human-in-the-loop.md` (본 PR 종료 후 삭제)
- 기존 흐름: `docs/data_flow/agent/HITL_GATE_FLOW.md` (본 PR 에서 갱신)

### C. PatchNote

2026-04-18: 최초 작성. 브레인스토밍 세션 결과 기반, approach 1(big-bang 단일 PR) + 스코프 A(최소 교체) 확정.
