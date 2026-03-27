# Agent Service — Patterns & Conventions

Updated: 2026-03-26

- **Single instance:** `OpenAIChatAgent` is created once; `initialize_async()` is called in lifespan after all sync inits. It fetches MCP tools and creates the agent with `MongoDBSaver` checkpointer and `CustomAgentState`. `is_healthy()` returns `False` until then (swallowed via `swallow_health_error=True`).
- **Persona injection:** `ChatMessage.persona_id` (default `"yuri"`) maps to a key in `yaml_files/personas.yml`. Persona text is prepended as `SystemMessage` at `stream()` time — not stored in the model field.
- **Checkpointer (LangGraph `MongoDBSaver`):** All message persistence is automatic. `thread_id` (= `session_id`) is passed via `config["configurable"]["thread_id"]`. No manual save calls needed.
- **`CustomAgentState`:** Extends `AgentState` with `user_id`, `agent_id`, `pending_tasks: list[PendingTask]`, `ltm_last_consolidated_at_turn: int`, `knowledge_saved: bool`. Defined in `state.py`.
- **`SessionRegistry`:** Thin MongoDB wrapper in `session_registry.py`. `upsert(thread_id, user_id, agent_id)` is called by handlers/channel_service at the start of each turn to keep the session listing current.
- **`context` parameter:** `stream()` and `invoke()` accept `context: dict | None` forwarded to `astream`/`ainvoke`. Callers set `context={"reply_channel": ...}` for channel routing. `DelegateTaskTool` reads `runtime.context["reply_channel"]` to stamp tasks.
- **`user_id`/`agent_id` in state:** `stream()` and `invoke()` include them in the astream/ainvoke input dict so LTM hooks can read them from state.
- **Middleware package:** `middleware/` contains all agent middleware — `delegate_middleware.py` and `ltm_middleware.py`.
- **DelegateToolMiddleware:** Injects a zero-arg `DelegateTaskTool` per request via `AgentMiddleware.awrap_model_call()`. Tool returns a `Command` to update `pending_tasks` atomically.
- **LTM middleware (`ltm_middleware.py`):** Two hooks wired in `create_agent(middleware=[...])`:
  - `before_model(ltm_retrieve_hook)` — async; searches LTM using the latest `HumanMessage` text, injects result as `SystemMessage` before the model call. No-op if LTM unavailable or `user_id` empty.
  - `after_model(ltm_consolidation_hook)` — sync; fire-and-forget consolidation every 10 `HumanMessage` turns via `asyncio.create_task`.
- **Memory I/O:** LTM retrieval and consolidation are fully handled by middleware for all callers (WebSocket and channel). STM persistence is automatic via LangGraph checkpointer. Neither `handlers.py` nor `channel_service` has memory logic.
