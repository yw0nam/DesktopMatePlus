# F2: NanoClaw SSE Client

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Connect FastAPI to NanoClaw with SSE streaming.
- **I/O**: `POST /api/agent/run` -> SSE events -> Unity events.

## 2. Core Logic
- **Step 1**: Define request/response schemas for the run payload and SSE events.
- **Step 2**: Implement `NanoClawClient.run_agent()` as `AsyncIterator` using `httpx` SSE.
- **Step 3**: Implement `interrupt(session_id)` with explicit `POST /api/agent/interrupt`.
- **Step 4**: Implement `health_check()` to power circuit breaker logic.
- **Step 5**: Add retry and timeout policy:
  - Retry 2 times with backoff (500ms -> 1s).
  - First activity timeout 5s; treat `ping` or `token` as activity.
  - Circuit breaker opens after 3 consecutive failures for 30s.
- **Constraints**:
  - Persist `nanoclaw_session_id` per FastAPI session.
  - Never forward `tool_call` or `tool_result` to Unity; log only.

## 3. Usage
- Call `run_agent()` and stream `token` events to the Stream Interceptor.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [F3_stream_interceptor.md](F3_stream_interceptor.md)
- [task_nanoclaw/N1_sse_server.md](../task_nanoclaw/N1_sse_server.md)

### B. Test Scenarios
- SSE stream receives `token` events and yields them in order.
- `ping` keeps the stream active and avoids false 5s timeout.
- Circuit breaker opens after 3 failures and blocks requests for 30s.
- `interrupt(session_id)` returns success and ends streaming.
