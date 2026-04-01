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

Every task MUST pass all three phases before marking `cc:DONE`.

### Quick check

```bash
scripts/check-task.sh -k <keyword>
```

Where `<keyword>` is the task identifier (e.g. `irodori`, `tts`, `slack`).

### Phases

| Phase | Command | Pass condition |
|-------|---------|----------------|
| **1 — Lint** | `sh scripts/lint.sh` | Exit 0 (ruff + black + structural tests) |
| **2 — Unit tests** | `uv run pytest -k <keyword> -v` | All collected tests pass |
| **3 — E2E** | auto-run inside `check-task.sh` | Backend healthy + TTS demo exits 0 + no ERROR logs |

### Manual steps (if check-task.sh unavailable)

```bash
# Phase 1
sh scripts/lint.sh

# Phase 2
uv run pytest -k <keyword> -v

# Phase 3 (manual)
scripts/run.sh --bg
sleep 5
PORT=$(scripts/run.sh --port)
uv run python examples/realtime_tts_streaming_demo.py \
    --ws-url "ws://127.0.0.1:${PORT}/v1/chat/stream"
bash scripts/logs.sh --level ERROR
scripts/run.sh --stop
```

### Notes

- Phase 3 requires real external services (MongoDB, Qdrant). Skip with `--no-slow` flag if not available.
- `check-task.sh` picks a random port (5000-9999) to avoid collisions with the main app on 5500.
