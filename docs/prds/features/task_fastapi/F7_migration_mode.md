# F7: Migration Mode

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Switch between legacy agent and NanoClaw during rollout.
- **I/O**: `MIGRATION_MODE` env var -> agent selection.

## 2. Core Logic
- **Step 1**: Add `MIGRATION_MODE` with values `legacy|nanoclaw`.
- **Step 2**: Route chat requests to the selected pipeline.
- **Step 3**: Keep both pipelines functional until Phase 3 exit.
- **Constraints**:
  - Default to `legacy` in production until rollout approval.

## 3. Usage
- Set `MIGRATION_MODE=nanoclaw` to enable new pipeline.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [NANOCLAW_INTEGRATION_PRD.md](../NANOCLAW_INTEGRATION_PRD.md)

### B. Test Scenarios
- Default mode routes to legacy pipeline when env var is unset.
- `MIGRATION_MODE=nanoclaw` routes to NanoClaw pipeline.
- Mode switch does not break existing WebSocket sessions.
