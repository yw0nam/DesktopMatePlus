# F3: Stream Interceptor

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Relay tokens to Unity and trigger sentence-based TTS.
- **I/O**: SSE events -> WebSocket events + TTS task triggers.

## 2. Core Logic
- **Step 1**: Implement `StreamInterceptor.process_stream()` for streaming vs non-streaming agents.
- **Step 2**: On `token`, send `{type: "text"}` to Unity and append to buffer.
- **Step 3**: Detect sentence boundaries with `TextChunkProcessor` and trigger TTS.
- **Step 4**: On `done`, send `{type: "stream_end"}` and cleanup.
- **Constraints**:
  - Filter out `tool_call` and `tool_result` from Unity output.
  - Generate `turn_id` at stream start and include in all events.

## 3. Usage
- For PersonaAgent: enable streaming path.
- For Specialized Agents: skip Unity relay and only signal completion.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [F4_tts_task_spawner.md](F4_tts_task_spawner.md)
- [task_unity/U1_event_handlers.md](../task_unity/U1_event_handlers.md)

### B. Test Scenarios
- Tokens are relayed to Unity in the same order as received.
- Sentence detection splits Korean and English punctuation correctly.
- `tool_call` and `tool_result` never reach Unity output.
- `done` emits `stream_end` once per turn.
