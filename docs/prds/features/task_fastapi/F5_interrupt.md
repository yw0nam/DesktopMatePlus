# F5: Interrupt Flow (Distributed Sentinel)

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Stop streaming and audio immediately on user interrupt.
- **I/O**: Unity `interrupt` -> clear_queue + NanoClaw interrupt.

## 2. Core Logic
- **Step 1**: On Unity `{type: "interrupt"}`, close SSE stream and call NanoClaw interrupt.
- **Step 2**: Cancel all in-flight TTS tasks and flush audio queue.
- **Step 3**: Send `{type: "clear_queue"}` to Unity and mark turn as `INTERRUPTED`.
- **Constraints**:
  - End-to-end latency target: 50ms to `clear_queue`.
  - Cleanup must be idempotent if multiple interrupts arrive.

## 3. Usage
- Trigger on UI cancel button or new user message while streaming.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [task_nanoclaw/N4_interrupt.md](../task_nanoclaw/N4_interrupt.md)
- [task_unity/U2_audio_queue.md](../task_unity/U2_audio_queue.md)

### B. Test Scenarios
- Interrupt during streaming sends `clear_queue` within 50ms.
- Multiple interrupt events are idempotent (no duplicate cleanup errors).
- In-flight TTS tasks are cancelled and no new audio is sent.
- NanoClaw interrupt endpoint is called once per turn.
