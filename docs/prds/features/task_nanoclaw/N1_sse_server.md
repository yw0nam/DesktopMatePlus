# N1: SSE Server

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Provide `POST /api/agent/run` SSE endpoint for streaming.
- **I/O**: FastAPI request -> SSE events (token, tool_call, done, error, ping).

## 2. Core Logic
- **Step 1**: Add `src/sse-server.ts` with Express SSE response.
- **Step 2**: Bridge container runner output to SSE events.
- **Step 3**: Emit `ping` every 15s to keep the connection alive.
- **Step 4**: Validate API key via `X-API-Key` header.
- **Constraints**:
  - `token` events are only for PersonaAgent (streaming).
  - Specialized agents emit only final output via `done`.

## 3. Usage
- FastAPI connects with `POST /api/agent/run` and reads SSE events.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [task_fastapi/F2_sse_client.md](../task_fastapi/F2_sse_client.md)

### B. Test Scenarios
- SSE stream emits `token`, `done`, and `error` with correct schema.
- `ping` is sent every 15s when idle.
- Missing or invalid `X-API-Key` returns 401.
- Specialized agents emit only `done` without `token` events.
