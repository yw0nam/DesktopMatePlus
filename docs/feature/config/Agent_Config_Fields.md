# Agent Configuration Fields

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Configure OpenAI-compatible chat agent with LLM settings
- **I/O**: YAML → `OpenAIChatAgentConfig` Pydantic model

## 2. Core Logic

### OpenAIChatAgentConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `openai_api_key` | str | `$LLM_API_KEY` | API key (from env) |
| `openai_api_base` | str | `"http://localhost:55120/v1"` | Base URL for API |
| `model_name` | str | `"chat_model"` | Model name |
| `top_p` | float | `0.9` | Top-p sampling |
| `temperature` | float | `0.7` | Sampling temperature |
| `mcp_config` | Dict | `None` | MCP tool configuration |
| `support_image` | bool | `False` | Enable image inputs |

### MCP Configuration (Optional)

```yaml
mcp_config:
  "sequential-thinking":
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    transport: "stdio"
```

## 3. Usage

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

---

## Appendix

### A. Related Documents

- [Configuration System](./README.md)
- [Agent Service](../service/Agent_Service.md)
