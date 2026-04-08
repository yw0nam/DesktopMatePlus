#!/usr/bin/env bash
# babysit-collect.sh — Open PR status collector for the backend repo
#
# Output format (one line per PR, tab-separated):
#   REPO  NUMBER  TITLE  REVIEW_DECISION  MERGEABLE  DAYS_OLD  IS_DRAFT  LABELS
#
# REVIEW_DECISION values: APPROVED | CHANGES_REQUESTED | REVIEW_REQUIRED | "" (none)
# MERGEABLE values: MERGEABLE | CONFLICTING | UNKNOWN
# IS_DRAFT: true | false
# LABELS: comma-separated, empty if none

set -euo pipefail

REPOS=(
  "yw0nam/DesktopMatePlus"
)

NOW=$(date +%s)

for REPO in "${REPOS[@]}"; do
  if ! PRS=$(gh pr list --repo "$REPO" \
    --json number,title,reviewDecision,mergeable,updatedAt,isDraft,labels \
    --state open --limit 50); then
    echo "WARN: gh pr list failed for $REPO (check auth)" >&2
    continue
  fi

  echo "$PRS" | jq -r \
    --arg repo "$REPO" \
    --argjson now "$NOW" '
    .[] |
    ( .updatedAt | fromdateiso8601 ) as $updated |
    ( ($now - $updated) / 86400 | floor ) as $days |
    ( .labels | map(.name) | join(",") ) as $labels |
    [ $repo,
      (.number | tostring),
      .title,
      .reviewDecision,
      .mergeable,
      ($days | tostring),
      (.isDraft | tostring),
      $labels
    ] | join("\t")
  '
done
