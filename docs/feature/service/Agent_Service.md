# Agent Service

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: AI agent with LLM, tool calling, streaming, and memory integration
- **I/O**: Messages + Context → Streamed response events (tokens, tool calls, results)

## 2. Core Logic

### Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `initialize_model()` | - | `(BaseChatModel, BaseCheckpointSaver)` |
| `is_healthy()` | - | `(bool, str)` |
| `stream()` | messages, conversation_id, tools, persona, user_id, agent_id, stm_service, ltm_service | AsyncGenerator of events |

### Stream Event Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `stream_start` | Response begins | `turn_id`, `conversation_id` |
| `stream_token` | Token chunk | `chunk`, `node` |
| `tool_call` | Tool invocation | `tool_name`, `args`, `node` |
| `tool_result` | Tool response | `result`, `node` |
| `stream_end` | Response complete | `turn_id`, `conversation_id`, `content` |

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
    conversation_id="conv_001",
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
