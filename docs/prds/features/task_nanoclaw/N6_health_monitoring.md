# N6: Health and Monitoring

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Provide reliable health signals and streaming diagnostics.
- **I/O**: Health endpoint + logs -> FastAPI circuit breaker decisions.

## 2. Core Logic
- **Step 1**: Implement `/health` with container runner readiness checks.
- **Step 2**: Log per-session metadata: `session_id`, `nanoclaw_session_id`, `group`.
- **Step 3**: Emit counters for container crashes and interrupt success rate.
- **Constraints**:
  - Health calls must not spawn containers.

## 3. Usage
- FastAPI polls health every 30s and opens circuit on failures.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [task_fastapi/F8_health_monitoring.md](../task_fastapi/F8_health_monitoring.md)

### B. Test Scenarios
- `/health` returns OK without starting a container.
- Crash counter increments on container failure.
- Interrupt success rate metric is recorded.
