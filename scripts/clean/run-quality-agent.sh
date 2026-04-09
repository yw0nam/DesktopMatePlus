#!/usr/bin/env bash
# run-quality-agent.sh — Launch /quality-report command via claude CLI
#
# Cron schedule: 7 9 * * * (09:07 KST daily)
# Runs /quality-report command: garden.sh + check_docs.sh, writes a report, and opens a PR.

set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/anaconda3/bin:$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DATE=$(date +%Y-%m-%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)

cd "$REPO_ROOT"

claude --print "/quality-report"
