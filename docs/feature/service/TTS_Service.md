# TTS Service

Updated: 2026-03-15

## 1. Synopsis

- **Purpose**: Text-to-Speech synthesis with voice cloning support; emotion-to-motion/blendshape mapping for Unity avatar
- **I/O**: Text + emotion → `TtsChunkMessage` (audio_base64 + motion_name + blendshape_name)

## 2. Core Logic

### TTSService Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `generate_speech()` | text, reference_id, output_format, output_filename | `bytes \| str \| bool \| None` |
| `list_voices()` | — | `list[str]` (voice IDs) |
| `is_healthy()` | — | `(bool, str)` |

### Output Formats (generate_speech)

| Format | Return Type | Description |
|--------|-------------|-------------|
| `bytes` | `bytes` | Raw audio data |
| `base64` | `str` | Base64-encoded MP3 audio |
| `file` | `bool` | Saved to `output_filename` |

### Implementations

| Class | Voice Support | Notes |
|-------|--------------|-------|
| `VLLMOmniTTS` | Scans `ref_audio_dir/` at startup | Caches voice list; requires `.mp3` + `.lab` per voice |
| `FishSpeechTTS` | `[]` (server-managed) | Fish Speech server integration |

### EmotionMotionMapper

Maps emotion keyword → `(motion_name, blendshape_name)` for Unity avatar.

- Config: `yaml_files/tts_rules.yml` → `emotion_motion_map:` section
- Initialized at startup via `initialize_emotion_motion_mapper()`
- Falls back to `default` entry, then to hardcoded `neutral_idle` / `neutral`

```python
mapper = get_emotion_motion_mapper()
motion, blendshape = mapper.map("joyful")  # → ("happy_idle", "smile")
motion, blendshape = mapper.map(None)      # → ("neutral_idle", "neutral")
```

### synthesize_chunk() Pipeline

`src/services/tts_service/tts_pipeline.py`

Wraps `generate_speech()` + `EmotionMotionMapper` into a single `TtsChunkMessage`. **Never raises exceptions to caller.**

```python
async def synthesize_chunk(
    tts_service, mapper, text, emotion, sequence,
    tts_enabled=True, reference_id=None
) -> TtsChunkMessage:
```

| Condition | audio_base64 | motion_name |
|-----------|-------------|-------------|
| Success | base64 MP3 | from mapper |
| `tts_enabled=False` | `null` | from mapper |
| `generate_speech` returns `None` | `null` (+ backend log) | from mapper |
| Exception raised | `null` (+ backend log) | from mapper |

### Configuration

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

# yaml_files/tts_rules.yml
emotion_motion_map:
  joyful:    { motion: "happy_idle",   blendshape: "smile" }
  sad:       { motion: "sad_idle",     blendshape: "sad" }
  angry:     { motion: "angry_idle",   blendshape: "angry" }
  # ... 16 emotions total
  default:   { motion: "neutral_idle", blendshape: "neutral" }
```

## 3. Usage

```python
from src.services import get_tts_service, get_emotion_motion_mapper
from src.services.tts_service.tts_pipeline import synthesize_chunk

tts = get_tts_service()
mapper = get_emotion_motion_mapper()

# List available voices
voices = tts.list_voices()  # ["aria", "alice"]

# Synthesize a chunk (async, never raises)
chunk = await synthesize_chunk(
    tts_service=tts,
    mapper=mapper,
    text="Hello, how are you?",
    emotion="joyful",
    sequence=0,
    tts_enabled=True,
    reference_id="aria",
)
# chunk.audio_base64  → base64 MP3 or None
# chunk.motion_name   → "happy_idle"
# chunk.blendshape_name → "smile"
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [TTS Configuration](../config/TTS_Config_Fields.md)
- [MessageProcessor Event Flow](./MessageProcessor_Event_Flow.md)
- [TTS Chunk WebSocket Event](../../websocket/WebSocket_TtsChunk.md)
