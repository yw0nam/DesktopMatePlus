# U3: Connection Management

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Keep WebSocket connections stable and recover on failure.
- **I/O**: Connection events -> reconnect and auth flows.

## 2. Core Logic
- **Step 1**: Maintain `ws://backend:8000/ws` with configurable host.
- **Step 2**: Reconnect with exponential backoff (1s -> 2s -> 4s -> 30s).
- **Step 3**: Re-auth on reconnect via `{type: "authorize"}`.
- **Step 4**: Respond to `ping` with `pong`, detect 30s silence.
- **Constraints**:
  - Stop after 10 failed attempts and show a blocking error.

## 3. Usage
- Wrap connection logic in a single `WebSocketManager` class.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [task_fastapi/F2_sse_client.md](../task_fastapi/F2_sse_client.md)

### B. Test Scenarios
- Reconnect backoff sequence follows 1s -> 2s -> 4s -> 30s.
- Missing `ping` for 30s triggers reconnect.
- After 10 failed attempts, show blocking error state.
