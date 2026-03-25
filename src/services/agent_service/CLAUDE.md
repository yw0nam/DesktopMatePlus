# Agent Service — Patterns & Conventions

Updated: 2026-03-25

- **Single instance:** `OpenAIChatAgent` is created once; `initialize_async()` is called in lifespan after all sync inits. It fetches MCP tools and creates the agent. `is_healthy()` returns `False` until then (swallowed via `swallow_health_error=True`).
- **Persona injection:** `ChatMessage.persona_id` (default `"yuri"`) maps to a key in `yaml_files/personas.yml`. Persona text is prepended as `SystemMessage` at `stream()` time — not stored in the model field.
- **DelegateToolMiddleware:** Injects `DelegateTaskTool` per request via `AgentMiddleware.awrap_model_call()`. Session ID is read from `RunnableConfig.configurable` via `get_config()` — do not pass it as a constructor arg.
- **AgentService is a pure inference engine:** No STM/LTM dependency. `stream()` yields a `stream_end` event with `new_chats: list[BaseMessage]` — the messages generated this turn — for the caller to persist.
- **Memory I/O via `memory_orchestrator`:** `handlers.py` calls `memory_orchestrator.load_context()` (LTM prefix + STM history) before each turn. After `stream_end`, `event_handlers.py` fires `asyncio.create_task(save_turn(...))` as a background task. `stm_service`/`ltm_service` are passed via `turn.metadata` — not injected into AgentService.
