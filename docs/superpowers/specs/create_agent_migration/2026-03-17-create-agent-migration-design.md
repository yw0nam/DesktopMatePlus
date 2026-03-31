# Design: `create_agent` Migration (v2)

**Date:** 2026-03-17
**Branch:** `feat/version_2`
**Scope:** `backend/src/services/agent_service/`

---

## Overview

`langgraph.prebuilt.create_react_agent`을 `langchain.agents.create_agent`로 마이그레이션한다.
v1 spec의 에이전트 풀(Agent Pool) 및 매 요청 MCP fetch를 제거하고 최대한 단순화한다.

**v1 대비 주요 변경:**

- 에이전트 풀(`self._agents`) 제거 → 단일 `self.agent`
- MCP 도구 매 요청 fetch 제거 → 서비스 시작 시 1회 캐싱
- `MCPToolMiddleware` 축소 → `DelegateToolMiddleware` (DelegateTaskTool 주입만 담당)
- `get_config()` 전달 데이터 축소 → `session_id`만

---

## Goals

1. `create_agent`로 전환하여 deprecation 해소
2. `MemorySaver`, `get_state()`, `thread_id` 제거
3. MCP 도구 캐싱으로 TTFT 개선
4. `ChatMessage.persona` → `persona_id`로 변경, persona 텍스트는 서버 YAML 관리
5. 단일 에이전트 인스턴스 유지

**Out of scope:** `context_schema` 도입 (TODO로 명시만)

---

## Architecture

### 단일 에이전트 인스턴스

에이전트는 1개만 생성한다. `system_prompt`는 `create_agent()` 시점에 고정하지 않고,
`stream()` 호출 시 `messages` 리스트 선두에 `SystemMessage`를 삽입하여 전달한다.

```python
# stream() 내부
persona_text = self._personas.get(persona_id, "")
if persona_text:
    messages = [SystemMessage(content=persona_text)] + messages

await self.agent.astream({"messages": messages}, ...)
```

### 초기화 2단계

`initialize_model()`은 sync → LLM만 생성.
`initialize_async()`는 async → MCP 도구 fetch + 에이전트 생성.
`main.py` lifespan에서 `await agent_service.initialize_async()` 호출.

```python
class OpenAIChatAgent(AgentService):
    def initialize_model(self) -> BaseChatModel:
        return ChatOpenAI(...)  # LLM만

    async def initialize_async(self):
        # 1. MCP 도구 fetch (1회만)
        if self.mcp_config:
            async with MultiServerMCPClient(self.mcp_config) as client:
                self._mcp_tools = await client.get_tools()

        # 2. 단일 에이전트 생성
        self.agent = create_agent(
            model=self.llm,
            tools=self._mcp_tools,
            middleware=[DelegateToolMiddleware(stm_service=self.stm_service)],
        )
```

`self.agent`는 `initialize_async()` 이후에만 유효. `stream()` 호출 전 반드시 `initialize_async()` 완료 필요.

### Persona 설정 파일

```yaml
# yaml_files/personas.yml
personas:
  yuri:
    system_prompt: |
      You are Yuri, a friendly but slightly mischievous 3D desktop AI companion.
      ...
  kael:
    system_prompt: |
      You are Kael, ...
```

Emotion instructions (`tts_rules.yml` 로드)는 `initialize_async()` 시점에 각 `system_prompt` 끝에 append하여 `self._personas: dict[str, str]`에 저장.

### DelegateToolMiddleware

`DelegateTaskTool` 주입만 담당한다. MCP 도구 라우팅은 에이전트 내부 tool 노드가 처리.

```python
from langchain.agents.middleware.types import AgentMiddleware
from langgraph.config import get_config

class DelegateToolMiddleware(AgentMiddleware):
    def __init__(self, stm_service): ...

    async def awrap_model_call(self, request, handler):
        if not self.stm_service:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id")
        delegate = DelegateTaskTool(stm_service=self.stm_service, session_id=session_id)
        return await handler(request.override(tools=[*request.tools, delegate]))

    async def awrap_tool_call(self, request, handler):
        if request.tool_call["name"] != DelegateTaskTool.name:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id")
        delegate = DelegateTaskTool(stm_service=self.stm_service, session_id=session_id)
        return await handler(request.override(tool=delegate))
```

`stream()`에서 config:

```python
config = {"configurable": {"session_id": session_id}}
self.agent.astream({"messages": messages}, config=config, stream_mode=["messages", "updates"])
```

### 스트리밍 & 메모리 수집

`stream_mode=["messages", "updates"]` 사용.

| stream_type  | 용도                           |
|--------------|-------------------------------|
| `"messages"` | 토큰 스트리밍 (기존 로직 유지) |
| `"updates"`  | `new_chats` 수집 — STM 저장용 |

`create_agent` 노드 이름: `"model"` (모델 호출), `"tools"` (도구 실행).
기존 코드의 `"agent"` 노드 체크는 `"model"`로 교체.

```python
new_chats: list[BaseMessage] = []
async for stream_type, data in self.agent.astream(..., stream_mode=["messages", "updates"]):
    if stream_type == "updates":
        for node_name, updates in data.items():
            if node_name in ("model", "tools"):
                new_chats.extend(updates.get("messages", []))
    elif stream_type == "messages":
        msg, metadata = data  # metadata["langgraph_node"] 여전히 유효
        # 기존 토큰 스트리밍 로직
```

`MemorySaver`, `get_state()`, `thread_id`, `config` dict 제거.
수집된 `new_chats`는 기존 `save_memory()`에 그대로 전달.

---

## `AgentService` 추상 클래스 변경

```python
# initialize_model: checkpointer 제거
# 변경 전
def initialize_model(self) -> tuple[BaseChatModel, BaseCheckpointSaver]: ...

# 변경 후
def initialize_model(self) -> BaseChatModel: ...

# __init__ tuple unpack 제거
# 변경 전
self.llm, self.checkpoint = self.initialize_model()

# 변경 후
self.llm = self.initialize_model()

# initialize_async 추가 (기본 구현은 no-op)
async def initialize_async(self) -> None: ...

# stream() 시그니처
# 변경 전: persona: str
# 변경 후: persona_id: str
```

---

## `is_healthy()` 처리

`is_healthy()`는 `persona_id=""` (빈 문자열)로 호출. persona 텍스트가 없으면 `SystemMessage` 삽입 생략.

---

## File Changes

### `yaml_files/personas.yml` (신규)

- persona_id별 `system_prompt` 정의

### `src/models/websocket.py`

- `ChatMessage.persona: str` → `persona_id: str = "yuri"`
- 기존 긴 default persona 텍스트 제거

### `src/services/agent_service/service.py`

- `initialize_model()` 반환 타입: `tuple[BaseChatModel, BaseCheckpointSaver]` → `BaseChatModel`
- `__init__`: `checkpoint_config` 파라미터 및 `self.checkpoint` 제거, tuple unpack → single assign
- `initialize_async()` 추상 메서드 추가 (기본 no-op)
- `stream()` 추상 메서드: `persona: str` → `persona_id: str`

### `src/services/agent_service/openai_chat_agent.py`

- `initialize_model()`: LLM만 생성, `self.agent = None`, `self._mcp_tools = []` 초기화
- `initialize_async()`: MCP 도구 fetch + 캐싱 + 에이전트 생성
- `stream()`: persona 로드 → `SystemMessage` prepend → `self.agent.astream()`
- `_process_message()`: `stream_mode=["messages", "updates"]`, `get_state()` 제거
- `MemorySaver` import 및 사용 제거

### `src/services/agent_service/utils/delegate_middleware.py` (신규)

- `DelegateToolMiddleware` 클래스

### `src/services/service_manager.py`

- `initialize_agent_service()`에서 `stm_service` 주입 추가
- `main.py` lifespan에서 `await agent_service.initialize_async()` 호출 추가

### `src/services/websocket_service/manager/handlers.py`

- `persona=persona` → `persona_id=persona_id` 전달
- `tools` 파라미터 제거 (`DelegateTaskTool`은 미들웨어 담당)

---

## Invariants (변경하지 않는 것)

- `stream()` yield 이벤트 포맷 (`stream_start`, `stream_token`, `tool_call`, `tool_result`, `stream_end`, `error`)
- `StreamingBuffer` — TTS 청크 단위 플러시 로직
- `save_memory()` — STM/LTM 저장 파이프라인
- `AgentService` 추상 클래스 존재 (인터페이스 계약 유지)

---

## TODO

```python
# TODO: context_schema 도입 시:
#   - persona_id, session_id를 runtime context로 주입 → DelegateToolMiddleware에서 get_config() 불필요
#   - memory 도구들의 user_id/agent_id 주입도 ToolRuntime으로 처리
```
