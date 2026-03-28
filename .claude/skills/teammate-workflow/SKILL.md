# Teammate Workflow

You are an implementing teammate in the DesktopMatePlus Agent Teams workflow.
The Lead Agent has already completed Phases 1–5 (brainstorm → plan → review → distribute → worktree).
Your job covers **Phase 6 (implement) → Phase 7 (report) only**.

---

## MANDATORY: Use harness-work for ALL implementation

**DO NOT implement tasks directly. Always use:**

```
/harness-work breezing --no-discuss all
```

This is not optional. `harness-work` handles task tracking, lint checks, and commit formatting automatically. Implementing tasks manually bypasses these checks and will cause GP violations.

---

## Your Responsibilities

### Step 1 — Read context
- Read your repo's CLAUDE.md (original repo path, not worktree)
- Read `Plans.md` to confirm which `[target: this-repo/]` tasks are `cc:TODO`

### Step 2 — Work inside your assigned worktree
- You are already in `worktrees/{repo}-{slug}/`
- Never commit directly to `main` / `develop` / `feat/claude_harness`

### Step 3 — Execute ALL tasks via harness-work

```
/harness-work breezing --no-discuss all
```

harness-work will:
- Pick up `cc:TODO` tasks from Plans.md
- Implement each task
- Run lint/tests after each task
- Commit with conventional commit messages

### Step 4 — Report back to Lead Agent

When harness-work completes, send a message with:
- Tasks completed (list with cc:DONE status)
- Files created/modified
- Test/lint results
- Any blockers or escalations

---

## Golden Principles (enforced by harness-work)

See `docs/GOLDEN_PRINCIPLES.md` in workspace root.
Key rules:
- **GP-3**: No `print()` (backend) / no `console.log()` (nanoclaw)
- **GP-4**: No hardcoded config values
- **GP-10**: `sh scripts/lint.sh` must pass (backend) / `npm run build` must pass (nanoclaw)

## Escalate to Lead Agent if

- A task requires changes outside your assigned repo
- GP violation cannot be fixed without architectural decision
- harness-work fails after 2 retries
