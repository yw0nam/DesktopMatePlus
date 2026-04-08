# WebSocket: Stream Token

Updated: 2026-04-08

## 1. Synopsis

- **Purpose**: Real-time text token from agent — forwarded to client for text rendering
- **I/O**: Server sends `{ type: "stream_token", chunk, node? }` as each token is generated

## 2. Core Logic

### Direction

Server → Client

### Payload

```json
{
  "type": "stream_token",
  "chunk": "Hello! ",
  "node": "agent_response_node"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"stream_token"` |
| `chunk` | string | Yes | Text fragment (one or more characters) |
| `node` | string\|null | No | Processing node identifier |

### Behavior

- Multiple tokens emitted per turn — append each `chunk` to render text progressively
- Arrives **in parallel** with `tts_chunk` events (different purposes — see below)
- All tokens arrive before `stream_end`

**Role split:**

| Event | Purpose |
|-------|---------|
| `stream_token` | Real-time text display (append `chunk` to chat UI) |
| `tts_chunk` | Audio playback + VRM expression animation |

Both events are received by the client. Use `stream_token` for text, `tts_chunk` for audio/animation.

## 3. Usage

**C# (Unity):**

```csharp
void OnMessage(string json) {
    var msg = JsonUtility.FromJson<BaseMessage>(json);
    if (msg.type == "stream_token") {
        chatUI.AppendText(msg.chunk);  // real-time text rendering
    }
}
```

**JavaScript:**

```javascript
socket.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'stream_token') {
    chatTextEl.textContent += msg.chunk;
  }
};
```

---

## Appendix

### A. Related Documents

- [Stream Start](./WebSocket_StreamStart.md)
- [Stream End](./WebSocket_StreamEnd.md)
- [TTS Chunk](./WebSocket_TtsChunk.md)

### B. PatchNote

2026-04-08: "Server-internal only" 오류 수정 — stream_token은 클라이언트에 전달됨. Direction 교정. stream_token vs tts_chunk 역할 구분 명시. C# Unity 예제 추가.
