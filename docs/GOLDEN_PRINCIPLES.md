# Golden Principles

> **Purpose**: Invariants that must hold across all repos at all times.
> The Background Gardening Agent uses this as its checklist — each principle has a machine-verifiable DoD.
> When a violation is detected, a refactoring PR is opened automatically.

> **CONTRIBUTING**: This document is a protected invariant. Direct commits to this file are forbidden.
> All changes (adding, modifying, or removing a principle) **must go through a PR** and require explicit human approval before merge.

---

## GP-1: Architecture Layering

**Rule**: Dependency direction is strictly enforced. No reverse imports.

| Repo | Layer order (lower → higher) |
|------|------------------------------|
| `backend/` | core → models → services → api |

**Verify**: `uv run pytest tests/structural/test_architecture.py`

**Severity**: Critical — structural test failure blocks merge.

---

## GP-2: File Size Limits

**Rule**: No source file exceeds its repo's line limit.

| Repo | Limit | Exception |
|------|-------|-----------|
| `backend/` | 300 lines | — |

New violations must be fixed immediately — never added to `_KNOWN_*` sets without a remediation plan.

**Verify**: `uv run pytest tests/structural/test_architecture.py::test_file_sizes`

**Severity**: Major — lint fails on new violations.

---

## GP-3: No Bare Logging

**Rule**: No `print()` in `backend/` source files.

| Repo | Required | Banned |
|------|----------|--------|
| `backend/` | `from src.core.logger import logger` (Loguru) | `print()` |

**Verify**: `ruff check src/` (backend)

**Severity**: Major.

---

## GP-4: No Hardcoded Config

**Rule**: No magic strings, ports, URLs, or credentials in source code.

- `backend/`: all config via `settings` object or `yaml_files/`. No hardcoded `localhost`, port numbers, or API keys.

**Verify**: `grep -rn "localhost\|127\.0\.0\.1\|mongodb://" src/` must return zero hits (excluding test files and config loaders).

**Severity**: Critical (credential exposure) / Major (config values).

---

## GP-5: CLAUDE.md as Map, Not Encyclopedia

**Rule**: `CLAUDE.md` stays under 200 lines.
Detail goes in `docs/`, `docs/faq/`, or sub-directory `CLAUDE.md` files.

**Verify**: `wc -l CLAUDE.md` (≤ 200).

**Severity**: Minor — triggers a split suggestion PR.

---

## GP-6: Task Tracking via GitHub Issues

**Rule**: Every task must exist as a GitHub Issue before implementation starts.
Issues use label taxonomy (`type:*`, `severity:*`, `component:*`) for classification.

**Verify**: `gh issue list --repo yw0nam/DesktopMatePlus --state open`

**Severity**: Minor.

---

## GP-7: Worktree Isolation for Implementation

**Rule**: All implementation work happens inside a `git worktree` on a `feat/{slug}` branch.
Direct commits to `main`/`master` are forbidden during implementation.

**Verify**: `git log --oneline master..HEAD` should only show merge commits from worktree branches.

**Severity**: Major — work done on master branch must be rebased to a feature branch.

---

## GP-8: Lint Before Merge

**Rule**: `sh scripts/lint.sh` must pass (exit 0) in `backend/` before any merge.

**Verify**: CI / pre-merge gate.

**Severity**: Critical — blocks merge.

---

## GP-9: Archive Freshness

**Rule**: Completed work must be reflected by closing the corresponding GitHub Issue. When a feature is merged, its issue should be closed (automatically via `fixes #N` or manually).

**Verify**: `gh issue list --repo yw0nam/DesktopMatePlus --state open` — no stale issues for merged features.

**Severity**: WARN — garden.sh reports only.

---

## GP-10: Issue Hygiene

**Rule**: Open issues should be actionable. Stale issues (30+ days without activity) should be reviewed and either updated, closed, or labeled with a reason for keeping open.

**Verify**: `gh issue list --repo yw0nam/DesktopMatePlus --state open --json number,updatedAt`

**Severity**: WARN — garden.sh reports only; no merge block.

---

## Appendix: Gardening Agent Usage

The Background Gardening Agent runs each principle's **Verify** command and opens a PR when violations are found.
Priority order for automated remediation: GP-8 → GP-3 → GP-10 → GP-2 → GP-5 → GP-6.
GP-1 requires human review before auto-merge.
