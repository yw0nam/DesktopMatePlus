# F6: Memory Injection

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Provide recent context to NanoClaw and store durable memories.
- **I/O**: STM history -> NanoClaw context; conversation -> LTM updates.

## 2. Core Logic
- **Step 1**: Load STM history (last N messages) before each NanoClaw run.
- **Step 2**: Inject STM into `context.stm_history`.
- **Step 3**: Trigger LTM updates every 5 turns or when tokens > 2000.
- **Step 4**: Use an idempotency key (`session_id + turn_id + role + index`) when saving.
- **Constraints**:
  - STM pre-injection must not block streaming.
  - LTM updates run in background tasks only.

## 3. Usage
- Call in `handle_chat_message()` before `NanoClawClient.run_agent()`.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [F1_backend_rest_api.md](F1_backend_rest_api.md)
- [task_nanoclaw/N3_mcp_tools.md](../task_nanoclaw/N3_mcp_tools.md)

### B. Test Scenarios
- STM pre-injection includes only the last N messages.
- LTM update triggers on turn 5 and token threshold > 2000.
- Idempotency key prevents duplicate memory writes on retries.
