# U2: Audio Playback Queue

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Play audio in sequence and keep lip-sync aligned.
- **I/O**: `{type: "audio"}` events -> AudioClip playback.

## 2. Core Logic
- **Step 1**: Decode base64 to AudioClip and enqueue by `sequence`.
- **Step 2**: Play in order; wait for missing sequence up to 3s.
- **Step 3**: On `clear_queue`, flush all pending audio and stop playback.
- **Constraints**:
  - Max pending clips: 20; drop oldest if exceeded and notify UI.

## 3. Usage
- Use `AudioPlaybackQueue.Enqueue()` from the `audio` handler.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [U1_event_handlers.md](U1_event_handlers.md)
- [task_fastapi/F4_tts_task_spawner.md](../task_fastapi/F4_tts_task_spawner.md)

### B. Test Scenarios
- Audio clips play in sequence even if events arrive out of order.
- Missing sequence is skipped after 3s timeout.
- `clear_queue` stops playback and empties the queue.
- Exceeding 20 pending clips drops oldest and notifies UI.
