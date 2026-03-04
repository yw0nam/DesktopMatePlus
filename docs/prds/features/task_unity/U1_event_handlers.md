# U1: WebSocket Event Handlers

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Render streaming text and react to system events.
- **I/O**: WebSocket events -> UI state updates.

## 2. Core Logic
- **Step 1**: On `stream_start`, create a new text bubble and show thinking indicator.
- **Step 2**: On `text`, append content to the current bubble.
- **Step 3**: On `audio`, enqueue playback with `sequence` and emotion.
- **Step 4**: On `stream_end`, finalize bubble and hide indicator.
- **Step 5**: On `system_error`, show a non-chat toast and mark safe mode.
- **Constraints**:
  - All events must include `turn_id` and be routed to the correct UI context.

## 3. Usage
- Use a single dispatcher to map `type` -> handler function.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [U2_audio_queue.md](U2_audio_queue.md)

### B. Test Scenarios
- `stream_start` creates a new bubble and shows the indicator.
- `text` events append in order with no flicker.
- `system_error` shows a non-chat toast and safe mode state.
