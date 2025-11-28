# Configuration System

## 1. Synopsis

- **Purpose**: Manage application and service configurations using Pydantic models with YAML files
- **I/O**: YAML files (`yaml_files/`) → Validated Pydantic config objects

## 2. Core Logic

### Configuration Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Pydantic Models | `src/configs/*.py` | Type-safe validation |
| YAML Files | `yaml_files/` | Runtime configuration |
| Environment Variables | `.env` | Sensitive data (API keys) |

### Key Configuration Modules

| Module | Purpose |
|--------|---------|
| `settings.py` | Server, CORS, WebSocket settings |
| `agent.py` | LLM/Agent configuration |
| `tts.py` | Text-to-Speech settings |
| `vlm.py` | Vision-Language Model settings |
| `stm.py` | Short-Term Memory (MongoDB) |
| `ltm.py` | Long-Term Memory (mem0) |

### Loading Configuration

Initialize settings from YAML:

```python
from src.configs.settings import initialize_settings
settings = initialize_settings("yaml_files/main.yml")
```

Access settings anywhere:

```python
from src.configs.settings import get_settings
settings = get_settings()
```

### Main Configuration (`main.yml`)

```yaml
services:
  vlm_service: openai_compatible.yml
  tts_service: fish_speech.yml
  agent_service: openai_chat_agent.yml
  stm_service: mongodb.yml
  ltm_service: mem0.yml

settings:
  host: "127.0.0.1"
  port: 5500
  cors_origins: ["*"]
  debug: false
```

### Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | Agent | OpenAI API key |
| `VLM_API_KEY` | VLM | Vision model API key |
| `TTS_API_KEY` | TTS | TTS API key (optional) |
| `LTM_API_KEY` | LTM | mem0 LLM API key |
| `EMB_API_KEY` | LTM | Embedder API key |
| `NEO4J_USER` | LTM | Neo4j username |
| `NEO4J_PASSWORD` | LTM | Neo4j password |

## 3. Usage

### Initialize All Services

```python
from src.services import (
    initialize_tts_service,
    initialize_vlm_service,
    initialize_agent_service,
)

# Use default config paths
tts = initialize_tts_service()
vlm = initialize_vlm_service()
agent = initialize_agent_service()

# Or custom config path
tts = initialize_tts_service("custom/tts_config.yml")
```

### Custom YAML Config Example

```yaml
# yaml_files/services/tts_service/fish_speech.yml
tts_config:
  type: "fish_local_tts"
  configs:
    base_url: "http://localhost:8080/v1/tts"
    temperature: 0.7
    chunk_length: 200
```

---

## Appendix

### A. Configuration Field Reference

For detailed field specifications, refer to:

- [Settings Fields](./Settings_Fields.md)
- [Agent Config Fields](./Agent_Config_Fields.md)
- [TTS Config Fields](./TTS_Config_Fields.md)
- [VLM Config Fields](./VLM_Config_Fields.md)
- [STM Config Fields](./STM_Config_Fields.md)
- [LTM Config Fields](./LTM_Config_Fields.md)

### B. File Structure

```text
src/configs/
├── settings.py      # Application settings
├── agent.py         # Agent/LLM configuration
├── tts.py           # Text-to-Speech configuration
├── vlm.py           # Vision-Language Model configuration
├── stm.py           # Short-Term Memory configuration
└── ltm.py           # Long-Term Memory configuration

yaml_files/
├── main.yml
└── services/
    ├── agent_service/openai_chat_agent.yml
    ├── tts_service/fish_speech.yml
    ├── vlm_service/openai_compatible.yml
    ├── stm_service/mongodb.yml
    └── ltm_service/mem0.yml
```

### C. Related Documents

- [Service Layer](../service/README.md)
- [API Guide](../../API_GUIDE.md)
