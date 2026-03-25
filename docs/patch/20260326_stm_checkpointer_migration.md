# 2026-03-26 STM → LangGraph Checkpointer Migration

## Summary

Replaced the custom `MongoDBSTM` service (`stm_service/`) entirely with LangGraph's `MongoDBSaver` checkpointer. Message persistence is now automatic via LangGraph's checkpoint mechanism. Session metadata moves into `CustomAgentState`.

## What Changed

### Removed
- `src/services/stm_service/` — entire directory deleted
- `yaml_files/services/stm_service/mongodb.yml` — replaced by `yaml_files/services/checkpointer.yml`
- `memory_orchestrator.load_context()` and `save_turn()` — replaced by `load_ltm_prefix()`
- `stm=` parameter from all service call sites

### Added
- `src/services/agent_service/state.py` — `CustomAgentState`, `PendingTask`, `ReplyChannel`
- `src/services/agent_service/session_registry.py` — `SessionRegistry` (MongoDB collection wrapper for session listing)
- `src/services/agent_service/utils/ltm_consolidation_middleware.py` — `ltm_consolidation_hook` (`@after_model`, every 10 turns)
- `yaml_files/services/checkpointer.yml` — shared MongoDB config
- `GET /v1/stm/{session_id}/messages` — NanoClaw Option B fetch endpoint

### Modified
- **`OpenAIChatAgent`** — wired `MongoDBSaver` checkpointer, `CustomAgentState`, `context` param, `thread_id` config key
- **`DelegateTaskTool`** — async `_arun` returns `Command`; reads `runtime.context["reply_channel"]` instead of STM
- **`DelegateToolMiddleware`** — removed all STM dependencies
- **`disconnect_handler`** — uses `agent.aget_state` / `aupdate_state`
- **`callback.py`** — uses `agent.aget_state` / `aupdate_state`; `reply_channel` from task record (not session metadata)
- **`BackgroundSweepService`** — iterates via `session_registry.find_all()`, reads/writes state via `aget_state`/`aupdate_state`
- **`health.py`** — `check_stm()` → `check_mongodb()` (pings MongoDB client)
- **`/v1/stm` routes** — all 5 endpoints rewritten to use checkpointer + `SessionRegistry`
- **`main.py`** — `initialize_stm_service()` → `initialize_mongodb_client()`; sweep constructor updated

## Architecture Notes

- `session_id` (external API) = `thread_id` (LangGraph internal). Mapped in `OpenAIChatAgent`.
- `reply_channel` is now stored per-task in `PendingTask.reply_channel` (set by `DelegateTaskTool`), not at session level.
- `save_turn()` is gone. All message persistence happens automatically when the agent completes a turn via the checkpointer.
- LTM consolidation is triggered by middleware, not by `memory_orchestrator`.
