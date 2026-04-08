# WebSocket: TTS Chunk

Updated: 2026-04-08

## 1. Synopsis

- **Purpose**: Deliver synthesized TTS audio with VRM expression keyframe animation for one sentence chunk
- **I/O**: Server sends `{ type: "tts_chunk", sequence, text, audio_base64?, emotion?, keyframes }`

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "tts_chunk",
  "sequence": 0,
  "text": "Hello, how are you?",
  "audio_base64": "UklGR...(base64 WAV)...",
  "emotion": "joyful",
  "keyframes": [
    { "duration": 0.3, "targets": { "happy": 1.0 } }
  ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"tts_chunk"` |
| `sequence` | int | Yes | Chunk order within the turn, starting from 0 |
| `text` | string | Yes | Text that was synthesized |
| `audio_base64` | string\|null | Yes | WAV audio encoded as base64. `null` = skip audio playback (TTS disabled or synthesis failed) |
| `emotion` | string\|null | No | Detected emotion tag |
| `keyframes` | array | Yes | VRM expression timeline — always populated, even when `audio_base64` is null |

### keyframes Format

Each element is a `TimelineKeyframe`:

```json
{ "duration": float, "targets": { "expression_name": weight } }
```

| Sub-field | Type | Description |
|-----------|------|-------------|
| `duration` | float | Seconds to hold this expression (relative, not absolute). Accumulate for absolute timing. |
| `targets` | object | Map of VRM blend shape name → weight (0.0–1.0) |

**VRM expression names** (standard VRM humanoid blend shapes):

| Name | Emotion |
|------|---------|
| `happy` | Joy, delight |
| `sad` | Sadness, grief |
| `angry` | Anger, frustration |
| `surprised` | Surprise, shock |
| `neutral` | Default / thinking |

**Example — 2 sequential keyframes:**

```json
"keyframes": [
  { "duration": 0.2, "targets": { "surprised": 1.0 } },
  { "duration": 0.3, "targets": { "happy": 0.8 } }
]
```

Absolute timing: first keyframe 0–0.2 s, second 0.2–0.5 s.

### Behavior

- Sent once per sentence chunk during streaming
- Always arrives **before** `stream_end` — guaranteed by TTS barrier
- `audio_base64 = null` when:
  - `tts_enabled: false` in `chat_message` (skip audio, still apply keyframes)
  - TTS synthesis failed (backend logs error, client degrades gracefully)
- `keyframes` is **always populated** — apply VRM animation even when audio is null
- Backend sends chunks as synthesis completes (not strictly in order). **Client must sort by `sequence`** before playback.

## 3. Usage

**C# (Unity):**

```csharp
void OnMessage(string json) {
    var msg = JsonUtility.FromJson<TtsChunkMessage>(json);
    if (msg.type != "tts_chunk") return;

    // Always apply VRM expression animation
    ApplyKeyframes(msg.keyframes);

    // Play audio only if available
    if (msg.audio_base64 != null) {
        byte[] wavBytes = Convert.FromBase64String(msg.audio_base64);
        PlayWav(wavBytes);
    }
}

void ApplyKeyframes(List<Keyframe> keyframes) {
    float t = 0f;
    foreach (var kf in keyframes) {
        foreach (var pair in kf.targets)
            vrm.SetExpressionWeight(pair.Key, pair.Value, startTime: t, duration: kf.duration);
        t += kf.duration;
    }
}
```

**JavaScript:**

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'tts_chunk') {
    applyKeyframes(msg.keyframes);
    if (msg.audio_base64) {
      const wavBytes = base64ToBytes(msg.audio_base64);
      audioQueue.enqueue(msg.sequence, wavBytes); // sort by sequence before playback
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

### B. PatchNote

2026-04-08: `motion_name`/`blendshape_name` → `keyframes` 구조로 전면 교체. 오디오 포맷 MP3 → WAV 수정. keyframes 포맷·타이밍·sequence 정렬 책임 명시. C# Unity 예제 추가.
