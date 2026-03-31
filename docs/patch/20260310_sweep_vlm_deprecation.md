# Release Notes - VLM Deprecation, Task Sweep Service, LTM Fix

Updated: 2026-03-10

## [feat/version_2] (2026-03-10)

> VLM service deprecated, background sweep service added, LTM turn counter bug fixed, and various test additions.

### Upgrade Steps

* `yaml_files/main.yml` now includes `task_sweep_service: sweep.yml`. Add this entry if you have a custom `main.yml`.
* Create `yaml_files/services/task_sweep_service/sweep.yml` (or copy from repository default).
* VLM endpoints and service remain functional but are deprecated. Migrate image analysis to Agent Service with `support_image: true`.

### Breaking Changes

* None for external clients. VLM is deprecated but not yet removed.

### New Features

* **Background Sweep Service** (`src/services/task_sweep_service/`)
  - Periodically scans all STM sessions and marks expired delegated tasks (pending/running) as `failed`.
  - Configurable via `yaml_files/services/task_sweep_service/sweep.yml`:
    - `sweep_interval_seconds` (default: 60) — scan frequency.
    - `task_ttl_seconds` (default: 300) — max age before auto-fail.
  - Integrated into FastAPI lifespan (auto-start/stop).

* **`STMService.list_all_sessions()`** (`src/services/stm_service/`)
  - New abstract method + MongoDB implementation.
  - Returns all sessions across all users/agents (used by sweep service).

### Bug Fixes

* **LTM turn counter counts only HumanMessages** (`src/services/agent_service/service.py`)
  - Previously: `current_turn = len(history) // 2` — incorrect when history contains tool messages, system messages, etc.
  - Now: `current_turn = sum(1 for m in history if isinstance(m, HumanMessage))`.
  - Slice start for consolidation also corrected to find the exact HumanMessage position.

### Deprecations

* **VLM Service deprecated** (`src/services/vlm_service/`, `src/services/health.py`)
  - VLM health check removed from `HealthService`.
  - `service_manager.py` marked with deprecation comment.
  - Agent Service natively supports image+text (`support_image: true` in agent config).
  - Commit: `b05d15f` — "Deprecated: VLM service will be removed."

### Other Changes

* **TTS config export**: `VLLMOmniTTSConfig` now exported from `src/configs/tts/__init__.py`.
* **Formatting**: Ruff formatting applied across existing files (`b33da93`).
* **Tests**: Added `test_real_e2e.py`, `test_background_sweep.py`, `test_ltm_consolidation.py`, `test_tts_synthesis.py`, WebSocket service tests.
* **Scripts**: Added `scripts/mock_callback.sh` for FastAPI delegation debugging.

### Related Documents

* [Agent Service](../feature/service/Agent_Service.md)
* [STM Service](../feature/service/STM_Service.md)
* [LTM Service](../feature/service/LTM_Service.md)
* [VLM Service](../feature/service/VLM_Service.md) *(deprecated)*
* [Service Layer](../feature/service/README.md)
* [Configuration](../feature/config/README.md)
