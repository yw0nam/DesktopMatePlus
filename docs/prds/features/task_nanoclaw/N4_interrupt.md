# N4: Interrupt Handling

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Stop container execution on SSE close or explicit interrupt.
- **I/O**: SSE close or `POST /api/agent/interrupt` -> sentinel -> container stop.

## 2. Core Logic
- **Step 1**: On SSE `close`, create `_close` sentinel file.
- **Step 2**: Add `/api/agent/interrupt` to trigger the same path.
- **Step 3**: Enforce graceful shutdown then force terminate after 5s.
- **Constraints**:
  - Ensure partial responses are flushed before shutdown when possible.

## 3. Usage
- FastAPI calls interrupt during user cancel or safe mode.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [task_fastapi/F5_interrupt.md](../task_fastapi/F5_interrupt.md)

### B. Test Scenarios
- SSE `close` triggers `_close` sentinel creation.
- `POST /api/agent/interrupt` stops the container within 5s.
- Partial output is flushed before shutdown when available.
