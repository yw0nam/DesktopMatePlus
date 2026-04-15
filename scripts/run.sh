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
#   YAML_FILE                — override main config file (default: yaml_files/main.yml)
#   SKIP_SERVICE_CHECKS      — skip external dependency checks when set to true

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

MAIN_YAML_FILE="${YAML_FILE:-yaml_files/main.yml}"

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
_resolve_services_yml() {
    local main_yml="$1"
    local services_file

    if [[ ! -f "$main_yml" ]]; then
        return 0
    fi

    services_file=$(grep -E '^services_file:' "$main_yml" | sed 's/.*services_file:[[:space:]]*//' | tr -d '"' | head -1)
    if [[ -z "$services_file" ]]; then
        return 0
    fi

    if [[ "$services_file" = /* ]]; then
        echo "$services_file"
    else
        echo "$REPO_ROOT/yaml_files/$services_file"
    fi
}

_read_mongo_uri() {
    local yml="$1"
    if [[ -f "$yml" ]]; then
        grep -E 'connection_string:' "$yml" | sed 's/.*connection_string:[[:space:]]*//' | tr -d '"' | head -1
    fi
}

_read_qdrant_url() {
    local yml="$1"
    if [[ -f "$yml" ]]; then
        grep -A5 'provider: "qdrant"' "$yml" | grep -E '^\s+url:' | sed 's/.*url:[[:space:]]*//' | tr -d '"' | head -1
    fi
}

_read_neo4j_url() {
    local yml="$1"
    if [[ -f "$yml" ]]; then
        grep -A5 'provider: "neo4j"' "$yml" | grep -E '^\s+url:' | sed 's/.*url:[[:space:]]*//' | tr -d '"' | head -1
    fi
}

_parse_host_port_from_mongo_uri() {
    local uri="$1"
    local hostport

    hostport=$(echo "$uri" | sed -E 's|mongodb://([^@]*@)?([^/]+).*|\2|')
    echo "$hostport"
}

_parse_host_port_from_url() {
    local url="$1"
    local default_port="$2"
    local host port

    if [[ "$url" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*:// ]]; then
        host=$(echo "$url" | sed -E 's|^[a-zA-Z][a-zA-Z0-9+.-]*://([^:/]+).*|\1|')
        port=$(echo "$url" | sed -E 's|^[a-zA-Z][a-zA-Z0-9+.-]*://[^:]+:([0-9]+).*|\1|')
        [[ "$port" == "$url" ]] && port="$default_port"
    else
        host="${url%%:*}"
        port="${url##*:}"
        [[ "$port" == "$host" ]] && port="$default_port"
    fi

    echo "${host}:${port}"
}

_print_service_hint() {
    local service_name="$1"
    local endpoint="$2"
    local helper_script="$3"

    echo "[run.sh] ${service_name}에 연결할 수 없습니다 (${endpoint})." >&2
    echo "         먼저 다음 스크립트로 서비스를 실행하세요: bash ${helper_script}" >&2
}

_check_mongodb() {
    local uri="$1"
    local hostport host port

    hostport=$(_parse_host_port_from_mongo_uri "$uri")
    host="${hostport%%:*}"
    port="${hostport##*:}"
    port="${port%%/*}"

    if ! nc -z -w2 "$host" "$port" 2>/dev/null; then
        _print_service_hint "MongoDB" "$uri" "scripts/test_dbs/run_mongodb.sh"
        exit 1
    fi
}

_check_qdrant() {
    local url="$1"
    local hostport host port

    hostport=$(_parse_host_port_from_url "$url" "6333")
    host="${hostport%%:*}"
    port="${hostport##*:}"

    if ! nc -z -w2 "$host" "$port" 2>/dev/null; then
        _print_service_hint "Qdrant" "$url" "scripts/test_dbs/run_qdrant.sh"
        exit 1
    fi
}

_check_neo4j() {
    local url="$1"
    local hostport host port

    hostport=$(_parse_host_port_from_url "$url" "7687")
    host="${hostport%%:*}"
    port="${hostport##*:}"

    if ! nc -z -w2 "$host" "$port" 2>/dev/null; then
        _print_service_hint "Neo4j" "$url" "scripts/test_dbs/run_neo4j.sh"
        exit 1
    fi
}

if [[ "${SKIP_SERVICE_CHECKS:-false}" != "true" ]]; then
    SERVICES_YML=$(_resolve_services_yml "$MAIN_YAML_FILE")

    if [[ -n "$SERVICES_YML" ]]; then
        MONGO_URI=$(_read_mongo_uri "$SERVICES_YML")
        QDRANT_URL=$(_read_qdrant_url "$SERVICES_YML")
        NEO4J_URL=$(_read_neo4j_url "$SERVICES_YML")

        if [[ -n "$MONGO_URI" ]]; then
            _check_mongodb "$MONGO_URI"
        fi

        if [[ -n "$QDRANT_URL" ]]; then
            _check_qdrant "$QDRANT_URL"
        fi

        if [[ -n "$NEO4J_URL" ]]; then
            _check_neo4j "$NEO4J_URL"
        fi
    fi
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
    # E2E_LOG_FILE allows callers (e2e.sh) to use an isolated temp log path
    # instead of the shared daily log file. This prevents cross-run contamination.
    if [[ -n "${E2E_LOG_FILE:-}" ]]; then
        LOG_FILE="$E2E_LOG_FILE"
    else
        LOG_FILE="$LOG_DIR/app_$(date +%Y-%m-%d).log"
    fi
    echo "[run.sh] Starting in background on port $PORT (log: $LOG_FILE)"
    LOG_DIR="$LOG_DIR" nohup "${CMD_ARGS[@]}" >> "$LOG_FILE" 2>&1 &
    APP_PID=$!
    echo "$APP_PID" > "$REPO_ROOT/.run.pid"
    echo "$LOG_FILE" > "$REPO_ROOT/.run.logfile"
    echo "[run.sh] PID $APP_PID written to .run.pid"
else
    echo "[run.sh] Starting on port $PORT (foreground)"
    export LOG_DIR
    exec "${CMD_ARGS[@]}"
fi
