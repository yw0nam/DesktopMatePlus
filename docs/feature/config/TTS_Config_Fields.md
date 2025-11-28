# TTS Configuration Fields

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Configure Fish Speech TTS service settings
- **I/O**: YAML → `FishLocalTTSConfig` Pydantic model

## 2. Core Logic

### FishLocalTTSConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_url` | str | **Required** | Fish TTS server URL |
| `api_key` | str | `None` | API key (optional) |
| `seed` | int | `None` | Seed for deterministic output |
| `streaming` | bool | `False` | Enable streaming synthesis |
| `use_memory_cache` | str | `"off"` | Cache reference encodings |
| `chunk_length` | int | `200` | Synthesis chunk size (tokens) |
| `max_new_tokens` | int | `1024` | Max tokens to generate |
| `top_p` | float | `0.7` | Top-p sampling |
| `repetition_penalty` | float | `1.2` | Repetition penalty |
| `temperature` | float | `0.7` | Sampling temperature |

### Cache Options

| Value | Description |
|-------|-------------|
| `"on"` | Cache reference audio encodings |
| `"off"` | No caching (default) |

## 3. Usage

```yaml
# yaml_files/services/tts_service/fish_speech.yml
tts_config:
  type: "fish_local_tts"
  configs:
    base_url: "http://localhost:8080/v1/tts"
    seed: null
    streaming: false
    use_memory_cache: "off"
    chunk_length: 200
    max_new_tokens: 1024
    top_p: 0.7
    repetition_penalty: 1.2
    temperature: 0.7
```

---

## Appendix

### A. Related Documents

- [Configuration System](./README.md)
- [TTS Service](../service/TTS_Service.md)
