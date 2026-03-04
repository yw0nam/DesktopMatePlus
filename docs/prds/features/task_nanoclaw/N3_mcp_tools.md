# N3: MCP Tools for Backend Services

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Allow NanoClaw agents to call Backend VLM and Memory services.
- **I/O**: Tool input -> Backend REST -> structured tool output.

## 2. Core Logic
- **Step 1**: Implement `vlm_analyze_screen` in `container/agent-runner/src/tools`.
- **Step 2**: Implement `memory_load_history`, `memory_save`, `memory_search_ltm`.
- **Step 3**: Register tools in the agent runner `query()` call.
- **Constraints**:
  - All calls must include `X-API-Key`.
  - Return structured JSON only, no markdown in tool output.

## 3. Usage
- PersonaAgent calls tools on demand; STM is still pre-injected by FastAPI.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [task_fastapi/F1_backend_rest_api.md](../task_fastapi/F1_backend_rest_api.md)
- [task_fastapi/F6_memory_injection.md](../task_fastapi/F6_memory_injection.md)

### B. Test Scenarios
- Tool calls include `X-API-Key` and succeed with valid key.
- Tool errors are returned as structured JSON without markdown.
- `memory_save` followed by `memory_load_history` returns stored items.
