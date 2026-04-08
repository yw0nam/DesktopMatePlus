#!/usr/bin/env bash
# run-quality-agent.sh — Launch the quality-agent via claude CLI
#
# Cron schedule: 7 9 * * * (09:07 KST daily)
# Spawns quality-agent which runs garden.sh + check_docs.sh, writes a report, and opens a PR.

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/anaconda3/bin:$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DATE=$(date +%Y-%m-%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)
BRANCH="quality/report-${DATE}"

cd "$REPO_ROOT"

# Create the branch before spawning the agent (agent may need it to already exist)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")
if [[ "$CURRENT_BRANCH" != quality/* ]]; then
  git fetch origin master 2>/dev/null || true
  git checkout -B "$BRANCH" origin/master
fi

# Run quality-agent via claude CLI
claude --agent quality-agent --print "Run the daily quality check for ${DATE}. Write report to docs/reports/${YEAR}/${MONTH}/quality-${DATE}.md and open a PR."
