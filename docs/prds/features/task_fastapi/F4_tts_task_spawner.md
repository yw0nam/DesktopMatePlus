# F4: Async TTS Task Spawner

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Synthesize audio asynchronously without blocking token streaming.
- **I/O**: Sentence text -> audio event with sequence number.

## 2. Core Logic
- **Step 1**: Create `TTSTaskSpawner` with a concurrency semaphore (max 3).
- **Step 2**: On sentence completion, spawn a task and assign a sequence.
- **Step 3**: Send `{type: "audio"}` to Unity with `sequence`, `emotion`, and `duration_ms`.
- **Step 4**: Support `cancel_all()` for interrupts.
- **Constraints**:
  - Do not block the SSE stream.
  - Track in-flight task count and fail fast if queue exceeds 20 items.

## 3. Usage
- Use from `StreamInterceptor` when a sentence boundary is detected.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [F5_interrupt.md](F5_interrupt.md)
- [task_unity/U2_audio_queue.md](../task_unity/U2_audio_queue.md)

### B. Test Scenarios
- Concurrency never exceeds 3 in-flight tasks.
- Audio events include monotonic `sequence` starting at 0.
- `cancel_all()` stops all pending tasks during interrupt.
- Queue limit of 20 triggers drop and error event.
