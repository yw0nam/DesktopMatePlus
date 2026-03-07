# Agent Service

Updated: 2026-03-07

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

### Memory Injection Flow (Per Turn)

매 턴마다 아래 순서로 컨텍스트를 구성한 뒤 Agent에 주입합니다.

```
1. LTM search(query=user_input)  →  ltm_context: [SystemMessage]
2. STM get_chat_history()        →  stm_history: [BaseMessage, ...]
3. Inject: ltm_context + stm_history + [HumanMessage(current)]
4. LLM stream
5. stream_end yield
6. async(fire-and-forget): STM add_chat_history(new_chats)
```

**규칙:**
- LTM 결과는 STM history 앞에 SystemMessage로 선행 주입합니다. STM으로 덮어쓰지 않습니다.
- STM 저장은 `stream_end` yield 이후 `asyncio.create_task`로 비동기 처리합니다. stream_end를 블로킹하지 않습니다.

**LTM add_memory 정책 (Turn-based Consolidation):**
- 매 턴 저장은 단편적 정보가 누적되어 품질 저하 → **10턴마다 배치 consolidation** 방식 채택.
- `AgentService.LTM_CONSOLIDATION_TURN_INTERVAL = 10` (1턴 = human + AI 메시지 2개).
- STM 저장 후 전체 history 길이가 `INTERVAL * 2`의 배수일 때만 `ltm.add_memory(history[-20:])` 호출.
- 단편 메시지가 아닌 **배치 대화**를 Mem0에 전달해 Graph/Vector 추출 품질을 높입니다.

**[TODO] LTM consolidation 업그레이드 경로:**
- 현재: `len(history) % 20 == 0` 단순 카운트 방식 (STM 추가 read 비용 있음).
- 추후: STM `session.metadata`에 `ltm_last_consolidated_turn`, `ltm_token_count_since_last`를 저장하고 턴 수 OR 토큰 임계값(예: 3000) 중 먼저 도달한 조건으로 트리거. 재시작/멀티프로세스 안전.

**[TODO] 알려진 구현 버그 (수정 필요):**
- `handlers.py:213`: STM `get_chat_history()` 할당이 `message_history`를 통째로 덮어써 LTM 결과가 유실됩니다.
- `openai_chat_agent.py:194`: `save_memory()`가 동기 호출로 `stream_end` 전에 블로킹됩니다. `asyncio.create_task(async_save_memory(...))` 방식으로 교체해야 합니다.

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
