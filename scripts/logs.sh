#!/usr/bin/env bash
# logs.sh — thin wrapper around log_query.py
# Passes all arguments through to log_query.py.
# Log file is auto-detected (LOG_DIR env, .run.logdir, logs/).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

exec uv run python "$SCRIPT_DIR/log_query.py" "$@"
