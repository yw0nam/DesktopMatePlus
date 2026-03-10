# Agent Service

Updated: 2026-03-10

## 1. Synopsis

- **Purpose**: AI agent with LLM, tool calling, streaming, and memory integration
- **I/O**: Messages + Context → Streamed response events (tokens, tool calls, results)

## 2. Core Logic

### Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `initialize_model()` | - | `(BaseChatModel, BaseCheckpointSaver)` |
| `is_healthy()` | - | `(bool, str)` |
| `stream()` | messages, session_id, tools, persona, user_id, agent_id, stm_service, ltm_service | AsyncGenerator of events |

### Stream Event Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `stream_start` | Response begins | `turn_id`, `session_id` |
| `stream_token` | Token chunk | `chunk`, `node` |
| `tool_call` | Tool invocation | `tool_name`, `args`, `node` |
| `tool_result` | Tool response | `result`, `node` |
| `stream_end` | Response complete | `turn_id`, `session_id`, `content` |

### ID 시맨틱 정의

| ID | 의미 | 생성 주체 |
|----|------|-----------|
| `session_id` | 유저-에이전트 대화 세션 (영속) | WebSocket handler |
| `turn_id` | 단일 요청-응답 사이클, `stream_start`/`stream_end`에 포함 | `OpenAIChatAgent` |
| `thread_id` | LangGraph 내부 체크포인트 키 (클라이언트에 노출 안 됨) | `OpenAIChatAgent` 내부 |

### Memory Injection Flow (Per Turn)

매 턴마다 아래 순서로 컨텍스트를 구성한 뒤 Agent에 주입합니다.

```
1. LTM search(query=user_input)  →  ltm_context: [SystemMessage]
2. STM get_chat_history()        →  stm_history: [BaseMessage, ...]
3. Inject: ltm_context + stm_history + [HumanMessage(current)]
4. LLM stream
5. stream_end yield
6. asyncio.create_task(save_memory(...))  ← fire-and-forget, 이벤트 루프 블로킹 없음
```

**규칙:**
- LTM 결과는 STM history 앞에 SystemMessage로 선행 주입합니다. STM으로 덮어쓰지 않습니다.
- `save_memory()`는 `stream_end` yield 이후 `asyncio.create_task`로 비동기 실행됩니다. 내부 I/O는 `asyncio.to_thread()`로 스레드풀 위임합니다.

**LTM Consolidation 정책 (STM metadata 기반):**
- 매 턴 저장은 단편적 정보가 누적되어 품질 저하 → **10턴마다 배치 consolidation** 방식 채택.
- `AgentService.LTM_CONSOLIDATION_TURN_INTERVAL = 10` (1턴 = HumanMessage 1개, `sum(1 for m in history if isinstance(m, HumanMessage))` 방식).
- STM `session.metadata.ltm_last_consolidated_at_turn`을 읽어 `current_turn - last >= N` 조건으로 트리거.
- 슬라이스 시작점은 `last_consolidated` 번째 HumanMessage 위치를 순회하여 정확히 결정.
- 재시작/멀티프로세스 안전 (카운트가 DB에 영속됨). TOCTOU 중복 트리거 없음.

### Implementation: OpenAIChatAgent

- OpenAI-compatible LLM via LangChain
- MCP (Model Context Protocol) tool support
- LangGraph-based workflow with checkpointing
- STM/LTM memory integration

### Configuration

```yaml
# yaml_files/services/agent_service/openai_chat_agent.yml
llm_config:
  type: "openai_chat_agent"
  configs:
    openai_api_base: "http://localhost:55235/v1"
    model_name: chat_model
    temperature: 0.7
    top_p: 0.9
    support_image: true
```

## 3. Usage

```python
from src.services import get_agent_service, get_stm_service, get_ltm_service

agent = get_agent_service()
stm = get_stm_service()
ltm = get_ltm_service()

async for event in agent.stream(
    messages=[HumanMessage(content="Hello!")],
    session_id="conv_001",
    user_id="user_001",
    agent_id="agent_001",
    stm_service=stm,
    ltm_service=ltm,
):
    match event["type"]:
        case "stream_token":
            print(event["chunk"], end="")
        case "tool_call":
            print(f"Calling: {event['tool_name']}")
        case "stream_end":
            print(f"\nComplete: {event['content']}")
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [Agent Configuration](../config/Agent_Config_Fields.md)
