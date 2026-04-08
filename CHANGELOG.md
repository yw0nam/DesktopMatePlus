# Changelog

All notable changes to DesktopMatePlus Backend will be documented in this file.

## [Unreleased]

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
