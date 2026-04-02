# AGENTS.md — Development Flow

> **Project**: backend (DesktopMate+ Director)
> **Language**: Python 3.13 / FastAPI

---

## Agent Setup

| Agent | Role | Responsibilities |
|-------|------|-----------------|
| **Lead Agent** | Coordinator | Task distribution, review gate, production deploy decisions |
| **developer** | Implementer | TDD implementation, tests, lint, commit |
| **review-agent** | Reviewer | `/review` + `/cso` pre-merge gate |

## Workflow

```
Lead Agent                      developer
    │                            │
    │  1. Assign task            │
    │  (TaskCreate + spawn)      │
    │──────────────────────────> │
    │                            │  2. TDD implement
    │                            │  (test → code → lint → commit)
    │                            │
    │  3. Review (review-agent)  │
    │ <──────────────────────────│
    │                            │
    │  4. Pass / fix loop        │
    │──────────────────────────> │
```

## Key Commands

- `/teammate-workflow` — developer implementation workflow
- `/review` — pre-merge code review
- `/cso` — security audit (backend changes)
- `/investigate` — systematic debugging

## Task Completion Checklist (DoD)

Every task MUST pass all phases before marking `cc:DONE`.

### Full E2E check (preferred)

```bash
bash backend/scripts/e2e.sh
```

Must output `-> e2e: PASSED`. Requires MongoDB + Qdrant running.

### Per-task unit check

```bash
scripts/check-task.sh -k <keyword>
```

Where `<keyword>` is the task identifier (e.g. `irodori`, `tts`, `slack`).

### Phases

| Phase | Command | Pass condition |
|-------|---------|----------------|
| **1 — Lint** | `sh scripts/lint.sh` | Exit 0 (ruff + black + structural tests) |
| **2 — Unit tests** | `uv run pytest -k <keyword> -v` | All collected tests pass |
| **3 — E2E** | `bash scripts/e2e.sh` | STM/LTM/WS examples exit 0 + no app ERROR logs |

### Manual steps (if e2e.sh unavailable)

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

### Notes

- Phase 3 requires real external services (MongoDB, Qdrant). If unavailable, backend starts but `/health` returns 500 and examples will fail.
- `e2e.sh` picks a random port (7000-8999) to avoid collisions with the main app on 5500.
- LTM test auto-skips if Qdrant is not running (prints "LTM SKIPPED").
- **신규 BE-* 태스크**: Plans.md DoD에 `bash backend/scripts/e2e.sh PASSED` 체크 필수. 기존 cc:DONE 태스크 소급 제외.
