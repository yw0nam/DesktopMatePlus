# VLM Configuration Fields

## 1. Synopsis

- **Purpose**: Configure OpenAI-compatible Vision-Language Model settings
- **I/O**: YAML → `OpenAIVLMConfig` Pydantic model

## 2. Core Logic

### OpenAIVLMConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `openai_api_key` | str | `$VLM_API_KEY` | API key (from env) |
| `openai_api_base` | str | `"http://localhost:5530/v1"` | Base URL for VLM API |
| `model_name` | str | `"chat_model"` | Model name |
| `top_p` | float | `0.9` | Top-p sampling |
| `temperature` | float | `0.7` | Sampling temperature |

## 3. Usage

```yaml
# yaml_files/services/vlm_service/openai_compatible.yml
vlm_config:
  type: "openai_compatible"
  configs:
    temperature: 0.7
    top_p: 0.9
    model_name: "chat_model"
    openai_api_base: "http://localhost:5530/v1"
```

---

## Appendix

### A. Related Documents

- [Configuration System](./README.md)
- [VLM Service](../service/VLM_Service.md)
