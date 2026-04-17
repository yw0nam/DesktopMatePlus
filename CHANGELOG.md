# Changelog

All notable changes to DesktopMatePlus Backend will be documented in this file.

**READ [guidelines](docs/guidelines/changelog_guideline.md) FIRST BEFORE EDITING**

## [Unreleased]

### Changed

- migrate TODO.md + KNOWN_ISSUES.md to GitHub Issues — label taxonomy, milestones, script/doc references updated
- add HITL gate flow and proactive trigger data flow docs; Docker UID fix and dev volume mounts; services.docker.yml proactive config (#40)
- HitL Phase 2 — `HitLMiddleware` switched from binary dangerous/safe to a category-driven gate; READ_ONLY bypasses approval, all other categories interrupt. Unknown tools fail closed to DANGEROUS (#42, #60)
- `extra="forbid"` enforced on `FilesystemToolConfig`/`ShellToolConfig`/`WebSearchToolConfig`/`OpenAIChatAgentConfig` so stale YAML keys fail at startup (#42, #60)

### Added

- implement Human-in-the-Loop approval gate for dangerous tool calls (#36)
- add proactive talking feature — idle watcher, scheduled triggers, webhook endpoint (#38)
- add ProactiveConfig model, PromptLoader, IdleWatcher, ScheduleManager, ProactiveService (#38)
- add persona_id field to ConnectionState for per-connection persona tracking (#38)
- add POST /v1/proactive/trigger webhook endpoint with 200/400/404/503 responses (#38)
- add E2E tests for proactive webhook trigger and idle timeout (#38)
- `ToolCategory` enum (`read_only`/`state_mutating`/`external`/`dangerous`) + `category` field on `HitLRequestMessage` for client-side UX differentiation (#42, #60)
- per-builtin `hitl_overrides` + `mcp_default_hitl_category` + `mcp_hitl_overrides` YAML configuration, with operator warning when an MCP tool name shadows a built-in category (#42, #60)
- structural test `test_default_categories_coverage.py` enforcing that every built-in tool has a category entry (#42, #60)
- deterministic E2E test `test_read_only_tool_bypasses_hitl_via_middleware` verifying `interrupt()` is skipped for READ_ONLY tools (#42, #60)

### Fixed

- HitL interrupt payload without `category` now warns before fail-closed fallback to DANGEROUS (#42, #60)
- `scripts/e2e.sh`: preserve log on exit and sweep stale logs at next run start — enables post-hoc investigation of failed runs (#42, #60)
- `logger.warning(..., exc_info=True)` silently dropped tracebacks (loguru ignores the stdlib kwarg) — switched to `logger.opt(exception=True)` in `openai_chat_agent.py`; added `{exception}` to file format and `backtrace=True`/`diagnose=True` on both sinks (#42, #60)
- strip emotion emoji tags from `stream_token` chunks and `stream_end` content forwarded to Unity FE — FE cannot render emojis correctly (KI-23) (#39)
- TTS pipeline receives original chunks with emojis intact for emotion detection (#39)
- E2E test `test_stream_end_content_matches_tokens` updated to compare against stripped content (#39)
- add `persona_overrides` to `ProactiveConfig` — env-specific per-persona idle timeouts without modifying `personas.yml` (#39)
- e2e.sh: isolate log files per run using temp dir — prevents cross-run contamination from shared daily log (#39)
- address PR review comments (#36)
- fix persona_id="" bug in ProactiveService — now uses conn.persona_id instead of hardcoded empty string (#38)
- fix persona-specific idle timeouts not applied during background scanning — IdleWatcher now passes get_persona_fn through _loop() (#38)
- replace O(N) session lookup with O(1) UUID direct lookup in proactive route (#38)
- add stale entry cleanup for _triggered_connections and _last_proactive_at dicts (#38)
- add invalid session_id format handling (400 response) in proactive route (#38)
- Move resolved KI-18/19/20/21 from Open Issues to new Resolved Issues table in KNOWN_ISSUES.md (#35)
- Use `ErrorSeverity` enum for severity membership check in health endpoint test (#35)
- Add `.raise_for_status()` to E2E `stm_session` fixture teardown (#35)

## [2.5.0] - 2026-04-14

### Changed

- **BREAKING**: Decouple `pending_tasks` from LangGraph checkpointer state to MongoDB (`pending_tasks` collection) — callback/delegate/sweep now read/write directly via `PendingTaskRepository` (#30)
- Callback endpoint path changed from `/v1/callback/nanoclaw/{session_id}` to `/v1/callback/nanoclaw/{task_id}` (#30)
- `PendingTaskDocument.status` uses `Literal["running", "done", "failed"]` for type safety (#30)
- `update_status()` sets `completed_at` timestamp on terminal status transition (#30)
- `task_status_middleware` uses `completed_at` (not `created_at`) for recent-window filter (#30)
- Sweep service simplified: single `find_expirable` query replaces O(N sessions × M tasks) loop (#30)
- E2E test service orchestration: new `scripts/test_dbs/` helpers, dedicated test ports (#30)

### Added

- `PendingTaskRepository`: MongoDB repository with TTL index (7-day), `find_by_task_id`, `find_by_session_id`, `find_expirable`, `update_status` (#30)
- `task_status_inject_hook` middleware: injects delegated task status into system prompt before each model call (#30)
- `completed_at` field on `PendingTaskDocument` for accurate recent-task display (#30)

### Fixed

- `callback.py`: check `update_status` return value, log warning on no-op (race condition with TTL expiry) (#30)
- `delegate_task.py`: block webhook dispatch when DB insert fails — prevents silent partial-failure (#30)
- Remove hardcoded `/data1/yw0nam/db/qdrant` path from `run_qdrant.sh` (#30)
- Remove duplicate `import os` in `initialize_channel_service()` (#28)
- e2e.sh: prevent `rm -f /app_*.log` when `_LOG_DIR` is empty (#29)
- Add empty/whitespace string guard to `classify_health_severity()` — returns `RECOVERABLE` instead of `FATAL` (#28)
- Add null guard for `_LOG_DIR` in e2e.sh stale log cleanup (#29)

### Changed (PR #28, #29)

- Unify 10+ per-service YAML configs into 3 environment-specific standalone files (`services.yml`, `services.docker.yml`, `services.e2e.yml`) — replace `services:` dict with `services_file:` key (#29)
- Extract `classify_health_severity()` as module-level function from inner `_severity()`, strengthen `ModuleStatus.severity` type from `str | None` to `ErrorSeverity | None` (#28)
- Add `cleanup_async()` no-op base method to `AgentService`, remove `hasattr` guard in `main.py` (#28)
- Remove duplicate logging from tool factories, enrich ToolRegistry logs with config details (#28)
- e2e.sh: export `YAML_FILE=yaml_files/e2e.yml`, add null-guarded stale log cleanup, rename `FASTAPI_URL` → `BACKEND_URL` for `test_real_e2e.py` (#29)
- Add `@pytest.mark.e2e` markers to `TestBackendConnectivity` and `TestBackendCallbackDirect` (#29)

- ToolGateMiddleware: defense-in-depth middleware that validates shell commands against whitelist and filesystem paths against allowed directories before tool execution (#27)
- Builtin Tool Registry: YAML-config-driven `ToolRegistry` enabling LangChain builtin tools (FileSystem, Shell with command whitelist, DuckDuckGoSearch) — all disabled by default (#25)
- Shell tool with `RestrictedShellTool`: command whitelist enforcement, dangerous shell character rejection, `shlex.split` + `shell=False` for injection prevention (#25)
- `ShellToolConfig` Pydantic validator: fail-fast when `enabled=True` with empty `allowed_commands` (#25)
- MCP client lifecycle fix: stateless `MultiServerMCPClient` pattern for `langchain-mcp-adapters` 0.2.2 with graceful degradation on failure (#26)
- `cleanup_async()` on `OpenAIChatAgent` for graceful MCP shutdown (#26)
- User Profile System: Structured user context storage (job, interests, schedule) with `UserProfileService` and `update_profile` agent tool (#23)
- Conversation Summarization: Automatic STM compression after configurable turn thresholds via `SummaryService` and `SummaryMiddleware` (#23)
- Profile Middleware: Automatic user profile injection into agent context for personalized responses (#23)
- `ConversationSummary` and `UserProfile` Pydantic models with validation (#23)
- 13 tests covering profile middleware, summary middleware, and profile tool functionality (#23)

### Changed

- Extract `_load_service_yaml()` shared helper to unify channel/sweep YAML loading with type guards for malformed YAML (#24)
- Unify channel/sweep YAML parsing into `service_manager.py` — moved inline YAML loading from `main.py::_startup()` into `initialize_channel_service()` and `initialize_sweep_service()`, matching the existing TTS/Agent/LTM pattern (#22)
- Agent state extended with `summary` field for conversation digest context (#23)
- OpenAIChatAgent now supports conversation summaries and user profiles in prompt context (#23)

### Fixed

- Prevent `TypeError` from `dict(None)` when YAML keys like `slack:` or `sweep_config:` exist with no value — replaced `dict(raw.get('key', {}))` with `raw.get('key') or {}` for safe None coalescence (#22)
- Slack service now properly handles session lifecycle with user-specific conversation tracking (#23)

### Security

- ToolGateMiddleware blocks shell metacharacters (`;|&\`$\n(){}`etc.) and path traversal attacks (`../../`) at middleware level (#27)
- Remove security whitelist exposure from log messages — blocked commands/paths no longer log allowed lists (#27)
- Remove `type: ignore[override]` suppression from ToolGateMiddleware (#27)

### Added

- Makefile with `lint`, `test`, `e2e`, `run`, `fmt`, `clean` targets wrapping existing scripts (#19)
- Dockerfile: Python 3.13-slim + uv 0.9.5, two-phase `uv sync` for optimal layer caching (#19)
- `docker-compose.yml`: backend + MongoDB 7 + Qdrant v1.14.0 with healthchecks and named volumes (#19)
- Docker-specific YAML configs (`docker.yml`, `checkpointer.docker.yml`, `mem0.docker.yml`) using compose service names (#19)
- Structural tests for DevEx files (`test_devex_files.py` — 14 tests) (#19)
- `src/core/error_classifier.py`: project-wide `ErrorClassifier` + `ErrorSeverity` promoted from websocket-only (#20)
- `SlackService.cleanup()` and `cleanup_channel_service()` for graceful Slack disconnect on shutdown (#20)
- `reset_mongo_client()` in `service_manager.py` for clean same-process restart (#20)
- `severity` field on `ModuleStatus` health response (transient/recoverable/fatal) (#20)
- `WebSocketManager.close_all()` with `asyncio.gather` for parallel connection drain (#20)
- 24 TDD tests covering ErrorClassifier, shutdown cleanup, and WS manager close_all (#20)

### Changed

- Quality report 2026-04-09: TODO.md 라인 수 정정, GP-8 Violations Summary 추가, black 권고 정확도 개선 (#17)
- `_shutdown()` in `main.py` now follows reverse init order: sweep → channel → websocket → mongo (#20)
- `ErrorClassifier` in websocket_service refactored as backward-compatible subclass extending core (#20)
- `service_manager._initialize_service()` now logs severity-aware error messages (#20)

### Fixed

- KI-1: Add `IRODORI_TTS_BASE_URL` env var override for hardcoded TTS base_url, guarded by engine type check (#21)
- KI-4: Add non-root `appuser` to Dockerfile with proper `/app` ownership (#21)
- KI-6: Fix `SlackService.cleanup()` to use `getattr + not session.closed` pattern for safe aiohttp session teardown (#21)
- Gemini review: Guard `_apply_tts_env_overrides` with `tts_config.type == 'irodori'` to prevent `ValidationError` on non-irodori engines (#21)

- `docs/QUALITY_SCORE.md`: GP-8 violation 누락 수정, violations 요약 문구 현행화 (#17)
- Pinned uv to v0.9.5 in Dockerfile for reproducible builds (#19)
- Qdrant healthcheck uses curl (available in stock image) instead of wget (#19)

---

_Merged PRs below this line are from previous sessions._

### Changed

- Standalone 전환: nanoclaw, desktop-homunculus, Director-Artisan 크로스레포 참조 전부 제거
- AGENTS.md를 OMC 네이티브 subagent_type 기반으로 전면 교체 (executor, code-reviewer, security-reviewer 등), TDD 필수화
- Golden Principles를 backend-only 10개로 재정렬 (GP-5 Delegation, GP-6 NanoClaw, GP-13 DH MOD 제거)
- 태스크 트래킹 Plans.md → TODO.md 전환
- babysit: /review + /cso → code-reviewer + security-reviewer subagent, PR 머지 후 CHANGELOG 자동 업데이트 추가
- quality-agent: git worktree 격리 후 PR 생성 방식으로 전환

### Added

- `scripts/clean/`: garden.sh, check_docs.sh, babysit-collect.sh, cleanup-merged.sh, merged-recent.sh, pr-comments-filter.sh, run-quality-agent.sh 추가
- `.claude/agents/quality-agent.md`: 일일 GP 검증·리포트·PR 자동화 에이전트
- `.claude/commands/`: babysit, post-merge-sweeper, pr-pruner 워크플로우 커맨드
- `docs/GOLDEN_PRINCIPLES.md`: 13 → 10개 architectural invariants 문서화
- `docs/QUALITY_SCORE.md`: GP 검증 등급 매트릭스
- `docs/data_flow/chat/STREAM_TOKEN_TTS_FLOW.md`: stream_token/tts_chunk 내부 파이프라인 다이어그램
- `docs/data_flow/session/STM_LIFECYCLE.md`: STM 생성·복원·만료·정리 라이프사이클 다이어그램
- `docs/known_issues/KNOWN_ISSUES.md`: 기술 부채 추적 (KI-1: irodori.yml hardcoded IP)

### Fixed

- `scripts/clean/check_docs.sh`: PLANS_FILE Plans.md → TODO.md
- `scripts/clean/merged-recent.sh`: 크로스레포 참조 제거, 2>/dev/null auth 실패 묵살 수정
- `scripts/clean/babysit-collect.sh`: gh 실패 시 WARN 출력
- `scripts/clean/cleanup-merged.sh`: worktree remove --force → dirty check 후 조건부 제거
- `scripts/clean/garden.sh`: sed -i → atomic tmp+mv 패턴 (QUALITY_SCORE.md)
- `quality-agent.md`: REPORT_FILE 미선언, cd .. 경로 오류, push 실패 시 worktree 보존, dangling branch 정리

## [2.4.3] - 2026-04-04

### Added

- `POST /v1/tts/speak` endpoint — accepts `{ "text": "..." }` and returns `{ "audio_base64": "..." }` using the active TTS service. Returns 503 if service is unavailable or synthesis fails (including non-string return values like `False`).

## [2.4.2] - 2026-04-04

### Fixed

- Removed redundant `{e}` interpolation from two `logger.exception()` calls in `src/main.py` — `logger.exception` already captures and appends the exception automatically
- Replaced hardcoded relative paths (`"./yaml_files/..."`) with `pathlib.Path(__file__).resolve().parents[3] / ...` in `agent_factory.py` and `tts_factory.py` `__main__` blocks — fixes CWD-dependent path resolution

## [2.4.1] - 2026-04-03

### Fixed

- Moved 5 hardcoded network URLs (vLLM TTS, Irodori TTS, backend, NanoClaw, OpenAI agent) to YAML config or Pydantic `Settings` with env var overrides — eliminates GP-4 violations
- Replaced all bare `print()` calls in `src/` with Loguru logger — `logger.info/warning/error/exception` — eliminates GP-3 violations
- Cleared `_KNOWN_PRINT_FILES` and `_KNOWN_LOCALHOST_FILES` technical-debt sets in structural architecture tests

## [2.4.0] - 2026-04-01

### Added

- IrodoriTTSService: new TTS client with `IrodoriTTSConfig` — API URL, voice ID, and timeout configurable via `yaml_files/services/tts_service/irodori.yml`
- Emoji-based emotion detection: the model can now embed emojis (😊 😭 😠 etc.) directly in speech text to control IrodoriTTS voice style and expression; see `EMOJI_ANNOTATIONS.md` for the full reference table
- Edge-case guards for `output_filename=None` in TTS synthesis pipeline

### Removed

- Fish Speech TTS backend (`fish_speech.py`, `FishLocalConfig`) — fully replaced by IrodoriTTS

## [2.3.1] - 2026-04-01

### Fixed

- Fish Speech error logs are no longer silently swallowed — `logger.error` restored in the `except` block so TTS failures are visible ([3fe1836])
- Fish Speech TTS now serializes synthesis requests through an `asyncio.Queue` worker — concurrent synthesis calls no longer race, and hung requests time out after 120s ([3fe1836])
- `stream_token` events are now forwarded to WebSocket clients in addition to the internal STM event bus — the frontend can display text as it streams ([3fe1836])

## [2.3.0] - 2026-03-31

### Fixed

- Session continuity error: persona SystemMessage now injected only for new sessions (empty `session_id`), preventing invalid message order `[SM, HM1, AI1, SM, HM2]` on second turn that caused LLM API 400 errors ([bad7ef8])
- Suppress `stream_end` event after error to prevent clients receiving both error and end signals ([f0ff20c])
- `CustomAgentState` extended fields (`pending_tasks`, `ltm_last_consolidated_at_turn`, `knowledge_saved`) now use `NotRequired` to avoid LangGraph state merge errors ([f0ff20c])

## [2.2.0] - 2026-03-10

### Added

- Background sweep service for expired delegated task cleanup
- `STMService.list_all_sessions()` for cross-user session scanning
- vLLM Omni TTS support
- E2E tests for real service integration
- LTM consolidation tests
- TTS synthesis pipeline tests

### Changed

- LTM turn counter now counts only HumanMessages (previously incorrectly used `len(history)//2`)
- Improved turn counter slice logic for accurate consolidation

### Deprecated

- VLM service — Agent now natively supports image+text input

### Fixed

- LTM turn counter accuracy with mixed message types
- Turn slice calculation for LTM consolidation

## [2.1.0] - 2025-11-28

### Added

- Avatar configuration management via WebSocket
- Background image management via WebSocket
- Live2D model configuration support
- Updated documentation structure

### Changed

- Improved WebSocket API organization

## [2.0.0] - 2025-11-20

### Added

- Complete WebSocket streaming with real-time TTS chunks
- MongoDB-based STM for session management
- mem0 integration for long-term memory
- Customizable agent personas per message
- Non-blocking async memory save (no TTS blocking)
- Production-ready error handling and reconnection
- Full test coverage for all services

### Changed

- Major architectural improvements
- Enhanced memory system

## [1.0.0] - 2025-10-15

### Added

- Initial release with basic HTTP APIs
- WebSocket streaming foundation
- VLM and TTS service integration
- Core service architecture

---

For detailed technical changes and patch notes, see [docs/patch/](docs/patch/).
