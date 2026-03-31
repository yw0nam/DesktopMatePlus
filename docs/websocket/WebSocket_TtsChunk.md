# WebSocket: TTS Chunk

Updated: 2026-03-15

## 1. Synopsis

- **Purpose**: Deliver synthesized TTS audio with motion/blendshape data for one sentence chunk
- **I/O**: Server sends `{ type: "tts_chunk", sequence, text, audio_base64?, emotion?, motion_name, blendshape_name }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "tts_chunk",
  "sequence": 0,
  "text": "Hello, how are you?",
  "audio_base64": "//NExAA...(base64 MP3)...",
  "emotion": "joyful",
  "motion_name": "happy_idle",
  "blendshape_name": "smile"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"tts_chunk"` |
| `sequence` | int | Yes | Chunk order within the turn, starting from 0 |
| `text` | string | Yes | Text that was synthesized |
| `audio_base64` | string\|null | Yes | MP3 audio encoded as base64. `null` = skip audio playback (TTS disabled or synthesis failed) |
| `emotion` | string\|null | No | Detected emotion tag |
| `motion_name` | string | Yes | Unity AnimationPlayer motion to play |
| `blendshape_name` | string | Yes | Unity blendshape to apply |

### Behavior

- Sent once per sentence chunk during streaming (parallel to `stream_token`)
- Always arrives **before** `stream_end` — guaranteed by TTS barrier
- `audio_base64 = null` when:
  - `tts_enabled: false` in the `chat_message` (skip playback, still show motion)
  - TTS synthesis failed (backend logs error, client degrades gracefully)
- `motion_name` / `blendshape_name` are **always populated** — use them for avatar animation even when audio is null
- Process chunks in `sequence` order for correct lip-sync timing

## 3. Usage

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'tts_chunk') {
    // Always apply motion/blendshape
    avatar.playMotion(msg.motion_name);
    avatar.setBlendshape(msg.blendshape_name);

    // Play audio only if available
    if (msg.audio_base64) {
      const audio = base64ToAudio(msg.audio_base64);
      audioQueue.enqueue(msg.sequence, audio);
    }
  }
};
```

---

## Appendix

### A. Related Documents

- [Chat Message](./WebSocket_ChatMessage.md)
- [Stream End](./WebSocket_StreamEnd.md)
- [Stream Token](./WebSocket_StreamToken.md)
- [TTS Voices API](../api/REST_API_GUIDE.md)
