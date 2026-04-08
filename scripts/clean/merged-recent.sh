#!/usr/bin/env bash
# merged-recent.sh — PRs merged within the last N hours with unresolved comment counts
#
# Usage: merged-recent.sh [hours=24]
#
# Output (one line per merged PR):
#   REPO  NUMBER  TITLE  MERGED_AT  UNRESOLVED  TOTAL_INLINE

set -euo pipefail

HOURS="${1:-24}"
REPOS=(
  "yw0nam/DesktopMatePlus"
)

SINCE=$(date -u -d "${HOURS} hours ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
  || date -u -v "-${HOURS}H" +%Y-%m-%dT%H:%M:%SZ)  # macOS fallback

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for REPO in "${REPOS[@]}"; do
  PRS=$(gh pr list --repo "$REPO" \
    --state merged \
    --json number,title,mergedAt \
    --limit 30 2>/dev/null)

  # Filter to within the time window
  RECENT=$(echo "$PRS" | jq -r \
    --arg since "$SINCE" \
    '.[] | select(.mergedAt >= $since) | [.number, .title, .mergedAt] | @tsv')

  while IFS=$'\t' read -r NUMBER TITLE MERGED_AT; do
    [[ -z "$NUMBER" ]] && continue

    # Run comment filter; surface API errors to stderr (not silently ignored)
    FILTER_OUT=""
    if ! FILTER_OUT=$("${SCRIPT_DIR}/pr-comments-filter.sh" "$REPO" "$NUMBER" 2>&1); then
      echo "WARN: pr-comments-filter exited non-zero for ${REPO}#${NUMBER}: $(echo "$FILTER_OUT" | tail -1)" >&2
    fi
    SUMMARY=$(echo "$FILTER_OUT" | grep '^SUMMARY:' \
      || echo "SUMMARY: UNRESOLVED=0 RESOLVED=0 TOTAL=0")

    UNRESOLVED=$(echo "$SUMMARY" | grep -oP 'UNRESOLVED=\K[0-9]+')
    TOTAL=$(echo "$SUMMARY"      | grep -oP 'TOTAL=\K[0-9]+')

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$REPO" "$NUMBER" "$TITLE" "$MERGED_AT" "$UNRESOLVED" "$TOTAL"
  done <<< "$RECENT"
done
