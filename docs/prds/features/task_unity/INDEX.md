# Unity (Dumb UI) Tasks Index

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Implement Unity client handlers for streaming text and audio.
- **I/O**: WebSocket events -> UI rendering + audio playback.

## 2. Core Logic
- **U1**: Event handlers for `stream_start`, `text`, `audio`, `stream_end`, `system_error` -> [U1_event_handlers.md](U1_event_handlers.md)
- **U2**: Audio playback queue and lip-sync -> [U2_audio_queue.md](U2_audio_queue.md)
- **U3**: Connection management and heartbeat -> [U3_connection_management.md](U3_connection_management.md)

## 3. Usage
- Implement U1 first, then U2 for audio, then U3 for resilience.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [NANOCLAW_INTEGRATION_PRD.md](../NANOCLAW_INTEGRATION_PRD.md)
- [task_fastapi/INDEX.md](../task_fastapi/INDEX.md)
