# Task Completion Checklist (DoD)

Every task MUST pass all phases before marking `cc:DONE`.

## Full E2E check (preferred)

```bash
bash scripts/e2e.sh
```

Must output `-> e2e: PASSED`. Requires MongoDB + Qdrant running.

## Per-task unit check

```bash
scripts/check-task.sh -k <keyword>
```

Where `<keyword>` is the task identifier (e.g. `irodori`, `tts`, `slack`).

## Phases

| Phase | Command | Pass condition |
|-------|---------|----------------|
| **1 — Lint** | `sh scripts/lint.sh` | Exit 0 (ruff + black + structural tests) |
| **2 — Unit tests** | `uv run pytest -k <keyword> -v` | All collected tests pass |
| **3 — E2E** | `bash scripts/e2e.sh` | STM/LTM/WS examples exit 0 + no app ERROR logs |

## Manual steps (if e2e.sh unavailable)

```bash
# Phase 1
sh scripts/lint.sh

# Phase 2
uv run pytest -k <keyword> -v

# Phase 3 (manual)
PORT=$(( 7000 + RANDOM % 2000 ))
BACKEND_PORT=$PORT bash scripts/run.sh --bg
sleep 5
uv run python examples/test_stm.py --base-url "http://127.0.0.1:${PORT}"
uv run python examples/test_ltm.py --base-url "http://127.0.0.1:${PORT}"
uv run python examples/test_websocket.py --ws-url "ws://127.0.0.1:${PORT}/v1/chat/stream"
bash scripts/run.sh --stop
```

## Notes

- Phase 3 requires real external services (MongoDB, Qdrant). If unavailable, backend starts but `/health` returns 500 and examples will fail.
- `e2e.sh` picks a random port (7000-8999) to avoid collisions with the main app on 5500.
- LTM test auto-skips if Qdrant is not running (prints "LTM SKIPPED").
- 신규 태스크: TODO.md DoD에 `bash scripts/e2e.sh PASSED` 체크 필수.

## Appendix

```bash
uv run pytest                                              # all tests
uv run pytest tests/path/test_file.py                     # specific file
uv run pytest tests/path/test_file.py::TestClass::test_name  # single test
uv run pytest -m slow                                     # E2E tests (requires real services)
uv run pytest --cov=src                                   # with coverage
```

- `asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed.
- `slow` tests hit real MongoDB/Qdrant/LLM — skip in CI unless services are available.
- Update `examples/realtime_tts_streaming_demo.py` for any API or WebSocket interface changes.

### E. Linting & Formatting

```bash
sh scripts/lint.sh   # ruff + black + structural tests — run before ending any task
```

### F. Architecture Enforcement

```bash
uv run pytest tests/structural/ -v   # layer boundary + file size + convention tests (included in lint.sh)
```

- `tests/structural/test_architecture.py` — 9개 구조적 테스트
- Known-debt: `_KNOWN_*` sets에 기존 위반 추적. 신규 위반 → 즉시 fail. 해결 후 set에서 제거.
- Ruff 추가 규칙: `UP` (pyupgrade) / `SIM` (simplify) / `RUF` / `A` (builtins) / `TID` (tidy-imports)
