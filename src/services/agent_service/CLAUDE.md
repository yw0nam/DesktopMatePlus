# Agent Service — Patterns & Conventions

Updated: 2026-03-26

- **Single instance:** `OpenAIChatAgent` is created once; `initialize_async()` is called in lifespan after all sync inits. It fetches MCP tools and creates the agent with `MongoDBSaver` checkpointer and `CustomAgentState`. `is_healthy()` returns `False` until then (swallowed via `swallow_health_error=True`).
- **Persona injection:** `ChatMessage.persona_id` (default `"yuri"`) maps to a key in `yaml_files/personas.yml`. Persona text is prepended as `SystemMessage` at `stream()` time — not stored in the model field.
- **Checkpointer (LangGraph `MongoDBSaver`):** All message persistence is automatic. `thread_id` (= `session_id`) is passed via `config["configurable"]["thread_id"]`. No manual save calls needed.
- **`CustomAgentState`:** Extends `AgentState` with `user_id`, `agent_id`, `pending_tasks: list[PendingTask]`, `ltm_last_consolidated_at_turn: int`, `knowledge_saved: bool`. Defined in `state.py`.
- **`SessionRegistry`:** Thin MongoDB wrapper in `session_registry.py`. `upsert(thread_id, user_id, agent_id)` is called by handlers/channel_service at the start of each turn to keep the session listing current.
- **`context` parameter:** `stream()` and `invoke()` accept `context: dict | None` forwarded to `astream`/`ainvoke`. Callers set `context={"reply_channel": ...}` for channel routing. `DelegateTaskTool` reads `runtime.context["reply_channel"]` to stamp tasks.
- **DelegateToolMiddleware:** Injects a zero-arg `DelegateTaskTool` per request via `AgentMiddleware.awrap_model_call()`. Tool returns a `Command` to update `pending_tasks` atomically.
- **LTM consolidation middleware:** `ltm_consolidation_hook` (wrapped with `after_model()`) fires after each model call, counting `HumanMessage` turns. Every 10 turns it spawns a fire-and-forget `asyncio.create_task(_safe_consolidate_ltm(...))`.
- **Memory I/O:** `handlers.py` calls `load_ltm_prefix()` (LTM search only) before each turn and prepends the result. STM history is automatically loaded by the checkpointer — no explicit load call needed.
