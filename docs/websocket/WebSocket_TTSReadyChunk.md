# WebSocket: TTS Ready Chunk

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Indicate text chunk ready for TTS synthesis
- **I/O**: Server sends `{ type: "tts_ready_chunk", chunk, emotion? }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "tts_ready_chunk",
  "chunk": "Text ready for speech",
  "emotion": "happy"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"tts_ready_chunk"` |
| `chunk` | string | Yes | Text for TTS synthesis |
| `emotion` | string | No | Emotion hint for TTS |

### Behavior

- Sent during streaming for real-time TTS
- Synthesize as received (don't wait for full response)

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'tts_ready_chunk') {
    synthesizeSpeech(msg.chunk, msg.emotion);
  }
};
```

---

## Appendix

### A. Related Documents

- [TTS Synthesize (REST)](../api/TTS_Synthesize.md)
- [Stream Token](./WebSocket_StreamToken.md)
