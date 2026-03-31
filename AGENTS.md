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
