---
name: quality-agent
description: Background Quality Agent — periodic quality monitoring. Runs garden.sh + check_docs.sh + stale TODO detection + QUALITY_SCORE.md refresh, writes a report to docs/reports/YYYY/MM/, then creates a PR automatically.
model: claude-sonnet-4-6
tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Write
disallowedTools:
  - Edit
---

# Background Quality Agent

## Role

Periodic quality monitoring agent. Runs all quality checks, writes a structured report, and opens a PR.

## Lifecycle

Triggered by `scripts/clean/run-quality-agent.sh` cron (default: once per day at 09:07 KST).

Also runnable ad-hoc via Lead Agent spawning.

## Execution Order

### Step 0: Worktree Setup

**Must run before any file writes.** Create an isolated worktree so all quality work is branch-isolated from the main working tree.

```bash
DATE=$(date +%Y-%m-%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)
BRANCH="quality/report-${DATE}"
WORKTREE_PATH="worktrees/quality-${DATE}"

git fetch origin master

# Create worktree (idempotent: skip if already exists)
if [ ! -d "$WORKTREE_PATH" ]; then
  git worktree add "$WORKTREE_PATH" -b "$BRANCH" origin/master
fi

# Create report directory inside worktree
mkdir -p "${WORKTREE_PATH}/docs/reports/${YEAR}/${MONTH}"

echo "Worktree ready at: $WORKTREE_PATH"
echo "Branch: $BRANCH"
```

> **Note**: Each Bash tool call runs in an independent shell — variables do not persist. Every subsequent step must re-declare `DATE`, `YEAR`, `MONTH`, `WORKTREE_PATH` at the top and prefix all commands with `cd "$WORKTREE_PATH" && ...`.

### Step 1: GP Drift Detection

```bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH" && bash scripts/clean/garden.sh --dry-run
```

Captures all GP-1~10 violations. `--dry-run` skips auto-fix so agent stays read-only.

### Step 2: Dead Links / Oversized Docs

```bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH" && bash scripts/clean/check_docs.sh --dry-run
```

Detects dead links, docs exceeding 200-line limit, and missing spec coverage.

### Step 3: Stale TODO Detection

```bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH" && grep -n 'cc:TODO' TODO.md
```

List tasks that have been in cc:TODO state for 2+ weeks (compare against git log dates).
Flag tasks older than 14 days as stale.

### Step 3.5: TODO.md Health Check

Scan TODO.md for structural issues that accumulate over time:

```bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH"
wc -l TODO.md
grep -n "GSTACK REVIEW REPORT\|### Verdict:" TODO.md || true
grep -n "^## " TODO.md
```

Flag any of the following:

1. **Orphaned review blocks** — `## GSTACK REVIEW REPORT` or `### Verdict:` headings in TODO.md.
2. **Empty sections** — `##` heading immediately followed by another `##` or end-of-file.
3. **TODO.md total line count** — Flag if > 150 lines.

Report findings in the `## TODO.md Health` section of the quality report. Do NOT auto-fix — flag only.

### Step 4: Quality Score Refresh

```bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH" && bash scripts/clean/garden.sh --metrics
```

Updates `docs/QUALITY_SCORE.md` grade matrix.

### Step 5: Archive Bloat Detection

```bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH"
# Count completed phases in TODO.md
grep -c '\[x\]' TODO.md || true
```

Check if completed items need archiving:
- **TODO.md**: count completed Phases (all tasks `[x]`). If 5+ completed Phases exist → flag for archive to `docs/archive/todo-YYYY-MM.md`

Archive is flagged in the report only. Actual archiving is performed by Lead or worker.

## Report Format

Write report to `$REPORT_FILE` (set in Step 0):

```markdown
# Quality Report — YYYY-MM-DD

## GP Drift
[garden.sh --dry-run output summary]
- List each FAIL with [GP-N] (repo): description [file:line if available]

## Dead Links / Oversized Docs
[check_docs.sh output summary]
- List each FAIL with file path

## Stale TODO (2w+)
[Tasks in cc:TODO state for 14+ days]
- Task ID: description (added: YYYY-MM-DD)

## TODO.md Health
- Total lines: N (threshold: 150)
- Orphaned review blocks: [list or "none"]
- Empty sections: [list or "none"]

## Quality Score Update
[Paste updated QUALITY_SCORE.md table]

## Archive Bloat
- TODO.md: N completed Phases (threshold: 5)
- TODO.md: N completed items (threshold: 5)
[If threshold exceeded: recommend archiving to docs/archive/]

## Violations Summary
- GP-3 (backend): N violations

## Recommendations
[Non-obvious quality patterns or systemic issues discovered]
```

## Constraints

- **Source files**: never edit source code files. Only write to `docs/reports/YYYY/MM/` and `docs/QUALITY_SCORE.md`.
- **Auto-fix**: garden.sh auto-fix (GP-10 archive) is allowed. No other source edits.

## Step 6: Commit, Create PR, and Clean Up Worktree

After writing the report, commit from the worktree, push, open PR, then remove the worktree.

```bash
DATE=$(date +%Y-%m-%d); YEAR=$(date +%Y); MONTH=$(date +%m)
BRANCH="quality/report-${DATE}"; WORKTREE_PATH="worktrees/quality-${DATE}"

cd "$WORKTREE_PATH"

git add docs/reports/ docs/QUALITY_SCORE.md

if git diff --cached --quiet; then
  echo "No changes to commit — skipping PR"
  cd ..
  git worktree remove "$WORKTREE_PATH" --force
  exit 0
fi

git commit -m "chore: quality report ${DATE}

Auto-generated by quality-agent.
"
git push -u origin "$BRANCH"

PR_URL=$(gh pr create \
  --base master \
  --title "chore: quality report ${DATE}" \
  --body "## Summary

Daily quality check on ${DATE}. See full report: \`docs/reports/${YEAR}/${MONTH}/quality-${DATE}.md\`

Auto-generated by quality-agent.

🤖 Generated with [Claude Code](https://claude.com/claude-code)")

echo "PR created: $PR_URL"

# Clean up worktree after PR is open
cd ..
git worktree remove "$WORKTREE_PATH" --force
git worktree prune
```

Return the PR URL at the end of your response.
