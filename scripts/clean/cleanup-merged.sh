#!/usr/bin/env bash
# cleanup-merged.sh — Remove stale worktrees and merged remote branches
#
# Usage: cleanup-merged.sh [--dry-run]
#
# Covers:
#   - backend (master)
#
# Only removes branches matching our naming convention:
#   feat|fix|docs|refactor|chore|test|ci|build|quality|design

set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# FORMAT: repo_path|default_branch
REPOS=(
  "${REPO_ROOT}|master"
)

# Branch prefixes we own — never delete anything outside this set
OUR_PATTERN="^(feat|fix|docs|refactor|chore|test|ci|build|quality|design)/"

_run() {
  if $DRY_RUN; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

for ENTRY in "${REPOS[@]}"; do
  IFS='|' read -r REPO_PATH DEFAULT_BRANCH <<< "$ENTRY"
  [[ -d "$REPO_PATH/.git" ]] || continue

  echo ""
  echo ">>> $REPO_PATH  (default: $DEFAULT_BRANCH)"

  # Fetch + prune so merged detection is up to date
  git -C "$REPO_PATH" fetch --prune origin 2>/dev/null || true

  MAIN_ABS="$(git -C "$REPO_PATH" rev-parse --show-toplevel)"

  # ── 1. Stale worktrees ─────────────────────────────────────────────────────
  # Use --porcelain for space-safe path parsing
  current_path=""
  while IFS= read -r wt_line; do
    if [[ "$wt_line" == worktree\ * ]]; then
      current_path="${wt_line#worktree }"
    elif [[ "$wt_line" == branch\ refs/heads/* ]]; then
      branch="${wt_line#branch refs/heads/}"
      wt_path="$current_path"

      [[ "$wt_path" == "$MAIN_ABS" ]] && continue          # skip main worktree
      [[ "$branch" =~ $OUR_PATTERN ]] || continue           # skip non-ours

      if ! git -C "$REPO_PATH" branch -r --merged "origin/$DEFAULT_BRANCH" \
          | grep -q "origin/${branch}$"; then
        echo "  skip worktree (not merged): $wt_path  [$branch]"
        continue
      fi

      echo "  remove worktree: $wt_path  [$branch]"
      _run git -C "$REPO_PATH" worktree remove --force "$wt_path"
    fi
  done < <(git -C "$REPO_PATH" worktree list --porcelain)

  # ── 2. Merged local branches ────────────────────────────────────────────────
  git -C "$REPO_PATH" branch --merged "$DEFAULT_BRANCH" \
    | sed 's|^ *||' \
    | { grep -v "^\*\|^${DEFAULT_BRANCH}$\|^master$\|^main$\|^develop$" || true; } \
    | while read -r branch; do
        [[ "$branch" =~ $OUR_PATTERN ]] || continue

        echo "  delete local branch: $branch"
        _run git -C "$REPO_PATH" branch -d "$branch"
      done

  # ── 3. Merged remote branches ──────────────────────────────────────────────
  git -C "$REPO_PATH" branch -r --merged "origin/$DEFAULT_BRANCH" \
    | { grep -v 'HEAD' || true; } \
    | sed 's|^ *origin/||' \
    | { grep -v "^${DEFAULT_BRANCH}$\|^master$\|^main$\|^develop$" || true; } \
    | while read -r branch; do
        # only delete our branches
        [[ "$branch" =~ $OUR_PATTERN ]] || continue

        echo "  delete remote branch: $branch"
        _run git -C "$REPO_PATH" push origin --delete "$branch"
      done
done

echo ""
echo "cleanup-merged.sh done."
