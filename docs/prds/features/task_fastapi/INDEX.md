# FastAPI Orchestrator Tasks Index

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Split FastAPI work into implementable modules with clear inputs/outputs.
- **I/O**: Unity WebSocket -> FastAPI -> NanoClaw SSE -> Unity events + Backend REST.

## 2. Core Logic
- **F1**: Backend REST APIs (TTS, VLM, Memory, auth) -> [F1_backend_rest_api.md](F1_backend_rest_api.md)
- **F2**: NanoClaw SSE client (run/interrupt/health) -> [F2_sse_client.md](F2_sse_client.md)
- **F3**: Stream interceptor (token relay + sentence detection) -> [F3_stream_interceptor.md](F3_stream_interceptor.md)
- **F4**: Async TTS task spawner (audio events) -> [F4_tts_task_spawner.md](F4_tts_task_spawner.md)
- **F5**: Interrupt flow (distributed cancel) -> [F5_interrupt.md](F5_interrupt.md)
- **F6**: Memory injection (STM pre-inject + LTM update) -> [F6_memory_injection.md](F6_memory_injection.md)
- **F7**: Migration mode (legacy vs nanoclaw) -> [F7_migration_mode.md](F7_migration_mode.md)
- **F8**: Health and monitoring -> [F8_health_monitoring.md](F8_health_monitoring.md)

## 3. Usage
- Build the minimal streaming path: F1 -> F2 -> F3 -> F4.
- Add user control: F5.
- Harden: F6 -> F8.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [NANOCLAW_INTEGRATION_PRD.md](../NANOCLAW_INTEGRATION_PRD.md)
- [task_nanoclaw/INDEX.md](../task_nanoclaw/INDEX.md)
- [task_unity/INDEX.md](../task_unity/INDEX.md)
