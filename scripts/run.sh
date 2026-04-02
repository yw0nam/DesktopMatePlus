#!/usr/bin/env bash
# run.sh — worktree-aware FastAPI app launcher
#
# Usage:
#   scripts/run.sh           — foreground
#   scripts/run.sh --bg      — background (PID -> .run.pid)
#   scripts/run.sh --stop    — stop via .run.pid
#   scripts/run.sh --port    — print computed port only
#
# Environment:
#   BACKEND_PORT             — override computed port (used by e2e.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Port calculation
# ---------------------------------------------------------------------------
BASENAME=$(basename "$REPO_ROOT")

# Main branches: use port 5500
if [[ "$BASENAME" == "backend" || "$BASENAME" == "feat/claude_harness" ]]; then
    PORT=5500
else
    CKSUM=$(echo "$BASENAME" | cksum | cut -d' ' -f1)
    PORT=$(( 5500 + CKSUM % 100 ))
fi

# Allow override via BACKEND_PORT env var (used by e2e.sh for random port isolation)
if [[ -n "${BACKEND_PORT:-}" ]]; then
    PORT="$BACKEND_PORT"
fi

# Handle --port first (no side effects)
if [[ "${1:-}" == "--port" ]]; then
    echo "$PORT"
    exit 0
fi

# Handle --stop
if [[ "${1:-}" == "--stop" ]]; then
    PID_FILE="$REPO_ROOT/.run.pid"
    if [[ ! -f "$PID_FILE" ]]; then
        echo "[run.sh] .run.pid not found — app may not be running." >&2
        exit 1
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "[run.sh] Stopped process $PID."
        rm -f "$PID_FILE"
    else
        echo "[run.sh] Process $PID is not running." >&2
        rm -f "$PID_FILE"
        exit 1
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# External service checks
# ---------------------------------------------------------------------------
_check_mongodb() {
    local uri="$1"
    # Extract host:port from mongodb://[user:pass@]host:port/
    local hostport
    hostport=$(echo "$uri" | sed -E 's|mongodb://([^@]*@)?([^/]+).*|\2|')
    local host="${hostport%%:*}"
    local port="${hostport##*:}"
    # Remove db name if accidentally included
    port="${port%%/*}"
    if ! nc -z -w2 "$host" "$port" 2>/dev/null; then
        echo "[run.sh] MongoDB에 연결할 수 없습니다 ($uri)."
        echo "         서비스를 실행한 후 Enter 키를 누르세요..."
        read -r
    fi
}

_check_qdrant() {
    local url="$1"
    # url may be just "localhost" without scheme/port
    local host port
    if [[ "$url" =~ ^https?:// ]]; then
        host=$(echo "$url" | sed -E 's|https?://([^:/]+).*|\1|')
        port=$(echo "$url" | sed -E 's|https?://[^:]+:([0-9]+).*|\1|')
        [[ "$port" == "$url" ]] && port=6333
    else
        host="${url%%:*}"
        port="${url##*:}"
        [[ "$port" == "$host" ]] && port=6333
    fi
    if ! nc -z -w2 "$host" "$port" 2>/dev/null; then
        echo "[run.sh] Qdrant에 연결할 수 없습니다 ($url)."
        echo "         서비스를 실행한 후 Enter 키를 누르세요..."
        read -r
    fi
}

# Read MongoDB URI from yaml_files/services/checkpointer.yml
MONGO_URI=""
CHECKPOINTER_YML="$REPO_ROOT/yaml_files/services/checkpointer.yml"
if [[ -f "$CHECKPOINTER_YML" ]]; then
    MONGO_URI=$(grep -E 'connection_string:' "$CHECKPOINTER_YML" | sed 's/.*connection_string:[[:space:]]*//' | tr -d '"' | head -1)
fi

# Read Qdrant URL from yaml_files/services/ltm_service/mem0.yml
QDRANT_URL=""
MEM0_YML="$REPO_ROOT/yaml_files/services/ltm_service/mem0.yml"
if [[ -f "$MEM0_YML" ]]; then
    # Look for vector_store url under qdrant provider
    QDRANT_URL=$(grep -A5 'provider: "qdrant"' "$MEM0_YML" | grep -E '^\s+url:' | sed 's/.*url:[[:space:]]*//' | tr -d '"' | head -1)
fi

if [[ -n "$MONGO_URI" ]]; then
    _check_mongodb "$MONGO_URI"
fi

if [[ -n "$QDRANT_URL" ]]; then
    _check_qdrant "$QDRANT_URL"
fi

# ---------------------------------------------------------------------------
# LOG_DIR setup
# ---------------------------------------------------------------------------
LOG_DIR_NAME="logs/worktree-${BASENAME}"
LOG_DIR="$REPO_ROOT/$LOG_DIR_NAME"
mkdir -p "$LOG_DIR"
echo "$LOG_DIR" > "$REPO_ROOT/.run.logdir"

# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
BG_MODE=false
if [[ "${1:-}" == "--bg" ]]; then
    BG_MODE=true
fi

CMD_ARGS=(uv run uvicorn "src.main:get_app" --factory --port "$PORT" --reload)

if $BG_MODE; then
    LOG_FILE="$LOG_DIR/app_$(date +%Y-%m-%d).log"
    echo "[run.sh] Starting in background on port $PORT (log: $LOG_FILE)"
    LOG_DIR="$LOG_DIR" nohup "${CMD_ARGS[@]}" >> "$LOG_FILE" 2>&1 &
    APP_PID=$!
    echo "$APP_PID" > "$REPO_ROOT/.run.pid"
    echo "[run.sh] PID $APP_PID written to .run.pid"
else
    echo "[run.sh] Starting on port $PORT (foreground)"
    export LOG_DIR
    exec "${CMD_ARGS[@]}"
fi
