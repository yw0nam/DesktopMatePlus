# Testing Guide

Updated: 2026-04-14

## Commands

```bash
uv run pytest                                                # all tests
uv run pytest tests/services/test_tts_synthesis.py          # specific file
uv run pytest tests/api/test_health.py::TestHealth::test_check  # single test
uv run pytest -m slow                                        # E2E (real services)
uv run pytest -m e2e                                         # E2E integration tests
uv run pytest --cov=src                                      # with coverage
```

## Project-Specific Conventions

- `asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed
- `slow` marker: tests that hit real MongoDB / Qdrant / LLM — skipped in CI unless services are up
- `e2e` marker: integration tests requiring live backend + NanoClaw — use `@pytest.mark.e2e`
- `sh scripts/lint.sh` includes structural tests (`tests/structural/`) — always run before ending a task

## Directory Layout

Mirrors `src/`:

```
tests/
  ├── agents/          # Agent factory and service manager tests
  ├── api/             # REST endpoint tests (FastAPI TestClient)
  ├── config/          # Settings and environment tests
  ├── core/            # Core logic, middleware, message processing
  ├── services/        # Per-service tests (TTS, LTM, channel, etc.)
  ├── storage/         # DB and vector store integration tests
  ├── structural/      # Architecture enforcement (layer boundaries, file size)
  └── websocket/       # WebSocket gateway and message processor tests
```

## Shared Fixtures (`tests/conftest.py`)

| Fixture | Returns |
|---------|---------|
| `client` | FastAPI `TestClient` for REST endpoints |
| `sample_user_id` | `"test_user_123"` |
| `sample_thread_id` | `"test_thread_456"` |
| `initialize_test_settings` | Resets settings to test config |

## Structural Tests (`tests/structural/`)

9개 구조적 테스트 — layer boundary, file size, naming convention 검증.
`_KNOWN_*` sets에 기존 위반 추적. 신규 위반은 즉시 fail — set에 추가하지 말고 fix.

---

## Appendix

### PatchNote

2026-04-14: Added `e2e` marker documentation, updated date.
2026-04-05: 일반론(AAA 패턴, What to Test, 예제 코드) 제거 — 프로젝트 특화 정보만 유지.
2026-03-25: Moved from `.claude/rules/TESTING_GUIDE.md` → `tests/CLAUDE.md`.
