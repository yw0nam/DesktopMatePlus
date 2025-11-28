# TTS Service

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Text-to-Speech synthesis with voice cloning support
- **I/O**: Text + Reference ID → Audio bytes/base64/file

## 2. Core Logic

### Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `generate_speech()` | text, reference_id, output_format, output_filename | `bytes \| str \| bool \| None` |
| `is_healthy()` | - | `(bool, str)` |

### Output Formats

| Format | Return Type | Description |
|--------|-------------|-------------|
| `bytes` | `bytes` | Raw audio data |
| `base64` | `str` | Base64-encoded audio |
| `file` | `bool` | Saved to `output_filename` |

### Implementation: FishSpeechTTS

- Fish Speech server integration
- Reference audio voice cloning
- Configurable generation parameters

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
```

## 3. Usage

```python
from src.services import get_tts_service

tts = get_tts_service()

# Get audio as bytes
audio_bytes = tts.generate_speech(
    text="Hello, world!",
    reference_id="voice_001",
    output_format="bytes"
)

# Get audio as base64
audio_b64 = tts.generate_speech(
    text="Hello, world!",
    output_format="base64"
)

# Save to file
tts.generate_speech(
    text="Hello, world!",
    output_format="file",
    output_filename="output.wav"
)
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [TTS Configuration](../config/TTS_Config_Fields.md)
- [TTS API Endpoint](../../api/TTS_Synthesize.md)
