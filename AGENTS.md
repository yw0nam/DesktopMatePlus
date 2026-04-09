# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-09
**Commit:** b93e091
**Branch:** master

## OVERVIEW

DesktopMate+ backend — Python 3.13 / FastAPI server for AI desktop companion (Yuri). WebSocket streaming chat, TTS synthesis (IrodoriTTS), LangChain/LangGraph agent with MCP tools, MongoDB STM, mem0 LTM, Slack channel integration, background task sweep. No GPU inference in-process — calls OpenAI, vLLM, IrodoriTTS, MongoDB, Qdrant externally.

## STRUCTURE

```
backend/
├── src/
│   ├── api/routes/        # 6 FastAPI routers (stm, ltm, tts, websocket, slack, callback)
│   ├── configs/           # Pydantic settings + YAML loader (agent/, ltm/, tts/)
│   ├── core/              # logger.py (Loguru + request ID), middleware.py
│   ├── models/            # Pydantic V2 schemas per domain
│   ├── services/          # 7 services — see src/services/AGENTS.md
│   └── main.py            # App factory (create_app → get_app), lifespan, service init
├── tests/                 # Mirrors src/ — see tests/CLAUDE.md
├── docs/                  # API specs, WS protocol, data flows — see docs/CLAUDE.md
├── scripts/               # run.sh, e2e.sh, lint.sh, verify.sh, clean/
├── yaml_files/            # Runtime config (personas.yml, tts_rules.yml, services/*.yml)
├── worktrees/             # Git worktrees for feature isolation (auto-generated, ignore)
└── examples/              # Demo scripts (WS client, TTS streaming)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add API route | `src/api/routes/` + `src/models/` | Include router in `src/api/routes/__init__.py` |
| Add service | `src/services/<name>/` | Init in `service_manager.py`, register in `main.py` lifespan |
| Modify agent | `src/services/agent_service/` | See `agent_service/CLAUDE.md` |
| Add agent tool | `src/services/agent_service/tools/` | Follow existing tool pattern |
| Change TTS | `src/services/tts_service/` | See `tts_service/CLAUDE.md` |
| WebSocket protocol | `src/services/websocket_service/` | See `websocket_service/AGENTS.md` + `docs/websocket/CLAUDE.md` |
| Add env variable | `src/configs/settings.py` | Document in `docs/setup/ENVIRONMENT.md` |
| Add YAML config | `yaml_files/` | Load via `src/configs/` loader |
| Slack integration | `src/services/channel_service/` | See `channel_service/CLAUDE.md` |

## CONVENTIONS

- **Async-first**: All I/O uses `async/await`. No sync DB/API calls.
- **Type hints**: Strict. `|` for unions (3.10+ style). No `Any`.
- **No print()**: Always `loguru.logger`. See `src/CLAUDE.md`.
- **No hardcoded config**: Use `settings` object or YAML injection.
- **Factory pattern**: `create_app()` → `get_app()` for uvicorn.
- **Service singletons**: Module-level lazy init via `service_manager.py`.
- **Pydantic V2**: All request/response models. Validators, not manual checks.
- **Request ID**: Bound at middleware, threaded through all logs.

## ANTI-PATTERNS (THIS PROJECT)

- **Never** suppress types (`Any`, `type: ignore`).
- **Never** use `print()` — always `logger`.
- **Never** skip E2E tests — `bash scripts/e2e.sh` must pass before done.
- **Never** add DEBUG logs to production code paths.
- **Never** log sensitive data (passwords, tokens, PII).
- **Never** hardcode service URLs or credentials.
- **TDD mandatory**: RED → GREEN → REFACTOR. No exceptions.

## COMMANDS

```bash
# Dev server
uv run uvicorn "src.main:get_app" --factory --port 5500 --reload

# Testing (E2E is MANDATORY before marking done)
bash scripts/e2e.sh                    # E2E tests
uv run pytest                          # All tests
uv run pytest --cov=src                # With coverage

# Linting (includes structural tests)
bash scripts/lint.sh

# Custom YAML config
YAML_FILE=yaml_files/custom.yml uv run uvicorn "src.main:get_app" --factory
```

## COMPLEXITY HOTSPOTS

| File | Lines | Concern |
|------|-------|---------|
| `services/websocket_service/message_processor/processor.py` | 626 | Turn lifecycle, async task coordination |
| `services/websocket_service/message_processor/event_handlers.py` | 448 | Agent event → TTS chunk pipeline |
| `services/websocket_service/manager/websocket_manager.py` | 438 | Connection lifecycle, heartbeat |
| `services/service_manager.py` | 412 | Singleton init, async/sync bridging |
| `services/websocket_service/manager/handlers.py` | 393 | Message routing, chat turn management |

## CONTEXT-SENSITIVE DOCS

| Path | Content |
|------|---------|
| `src/CLAUDE.md` | Logging (format, levels, request ID) |
| `tests/CLAUDE.md` | Testing (pytest, fixtures, structural tests) |
| `docs/CLAUDE.md` | Doc authoring (200-line rule, structure) |
| `docs/websocket/CLAUDE.md` | WebSocket protocol (message types, lifecycle) |
| `src/services/tts_service/CLAUDE.md` | TTS (EmotionMotionMapper, synthesize_chunk) |
| `src/services/agent_service/CLAUDE.md` | Agent (LangGraph, middleware, memory) |
| `src/services/channel_service/CLAUDE.md` | Channel (Slack, session_lock, reply_channel) |
| `src/services/AGENTS.md` | Service layer (init order, deps, patterns) |
| `src/services/websocket_service/AGENTS.md` | WebSocket internals (processor, manager) |

## NOTES

- **Service init order matters**: TTS → Mapper → MongoDB → Agent → LTM → Channel → Sweep
- **Port calc**: Feature branches get port 5500 + (checksum % 100) via `scripts/run.sh`
- **Worktrees**: `worktrees/` is git worktree copies — ignore for code analysis, Note always make new worktree for each feature branch to isolate changes and simplify PRs.
- **Task tracking**: `TODO.md` with `cc:TODO` / `cc:WIP` / `cc:DONE` markers
