# TTS Configuration Fields

Updated: 2026-03-15

## 1. Synopsis

- **Purpose**: Configure TTS service settings and emotion-to-motion mapping for Unity avatar
- **I/O**: YAML → `FishLocalTTSConfig` / `EmotionMotionMapper`

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

### EmotionMotionMap Fields (`yaml_files/tts_rules.yml`)

Maps emotion keyword → Unity `(motion_name, blendshape_name)`. Used by `EmotionMotionMapper`.

```yaml
emotion_motion_map:
  joyful:     { motion: "happy_idle",      blendshape: "smile" }
  excited:    { motion: "excited_idle",    blendshape: "excited" }
  sad:        { motion: "sad_idle",        blendshape: "sad" }
  angry:      { motion: "angry_idle",      blendshape: "angry" }
  surprised:  { motion: "surprised_idle",  blendshape: "surprised" }
  fearful:    { motion: "fearful_idle",    blendshape: "fearful" }
  disgusted:  { motion: "disgusted_idle",  blendshape: "disgusted" }
  confused:   { motion: "confused_idle",   blendshape: "confused" }
  embarrassed:{ motion: "embarrassed_idle",blendshape: "embarrassed" }
  proud:      { motion: "proud_idle",      blendshape: "proud" }
  bored:      { motion: "bored_idle",      blendshape: "bored" }
  calm:       { motion: "calm_idle",       blendshape: "calm" }
  playful:    { motion: "playful_idle",    blendshape: "playful" }
  loving:     { motion: "loving_idle",     blendshape: "loving" }
  hopeful:    { motion: "hopeful_idle",    blendshape: "hopeful" }
  anxious:    { motion: "anxious_idle",    blendshape: "anxious" }
  default:    { motion: "neutral_idle",    blendshape: "neutral" }
```

- `default` entry is the fallback for unregistered or `null` emotions
- If `default` is missing entirely, hardcoded fallback `neutral_idle` / `neutral` is used
- Partial entries (e.g., only `motion` defined) use `default` for the missing field

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
- [Settings Fields](./Settings_Fields.md) — `tts_barrier_timeout_seconds`
