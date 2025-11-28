# TTS: Synthesize Speech

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Convert text to speech audio
- **I/O**: `POST { text, reference_id?, output_format? }` → `{ audio_data, format }`

## 2. Core Logic

### Endpoint

`POST /v1/tts/synthesize`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Text to synthesize (min 1 char) |
| `reference_id` | string | No | Voice reference ID for cloning |
| `output_format` | string | No | `"base64"` (default) or `"bytes"` |

### Response

**Success (200)**:
```json
{
  "audio_data": "base64_encoded_audio_string",
  "format": "base64"
}
```

**Errors**: `422` (missing/empty text), `401` (unauthorized), `500` (synthesis failed)

## 3. Usage

```bash
curl -X POST "http://127.0.0.1:5500/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{ "text": "Hello, world!", "output_format": "base64" }'
```

---

## Appendix

### A. JavaScript Playback Example

```javascript
fetch('http://127.0.0.1:5500/v1/tts/synthesize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'Hello!', output_format: 'base64' })
})
.then(res => res.json())
.then(data => {
  const audio = new Audio(`data:audio/wav;base64,${data.audio_data}`);
  audio.play();
});
```

### B. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [TTS Ready Chunk (WebSocket)](../websocket/WebSocket_TTSReadyChunk.md)
