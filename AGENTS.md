# AGENTS.md — Development Flow

> **Project**: backend (DesktopMate+ Director)
> **Language**: Python 3.13 / FastAPI

---

## Agent Setup

| Agent | Role | Responsibilities |
|-------|------|-----------------|
| **Claude Code** | PM | Task management, review, production deploy decisions |
| **Claude Code** | Worker | Implementation, tests, CI fixes, staging deploy |

## Workflow

```
Claude Code (PM)                Claude Code (Worker)
    │                            │
    │  1. Assign task            │
    │  (/handoff-to-claude)      │
    │──────────────────────────> │
    │                            │  2. Implement
    │                            │  /work
    │                            │
    │  3. Review result          │
    │ <──────────────────────────│
    │                            │
    │  4. Approve / request fix  │
    │──────────────────────────> │
```

## Key Commands

- `/harness-plan` — create/update task plan
- `/harness-work` — execute tasks
- `/harness-review` — code review
- `/harness-sync` — sync progress
