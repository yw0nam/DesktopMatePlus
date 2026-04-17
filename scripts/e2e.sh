#!/usr/bin/env bash
# e2e.sh — end-to-end verification pipeline for the backend
#
# Usage:
#   bash scripts/e2e.sh
#
# Prerequisites:
#   - MongoDB, Qdrant, Neo4j running with the ports from yaml_files/services.e2e.yml
#   - If a DB is not running, start it with scripts/test_dbs/run_<service>.sh
#   - TTS server optional (warning + skip if unavailable)
#
# Phases:
#   Phase 1  : Check MongoDB + Qdrant + Neo4j connectivity
#   Phase 1.5: Check TTS server (WARNING + SKIP if unavailable)
#   Phase 2  : Start backend on random port 7000-8999
#   Phase 3  : Wait for health (30s) — kill-0 + HTTP 200
#   Phase 4  : Run example scripts (test_stm, test_ltm, test_websocket)
#   Phase 5  : Check logs for app-level ERRORs
#   Phase 6  : Cleanup
#   Phase 7  : PASSED / FAILED summary

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

export YAML_FILE="yaml_files/e2e.yml"

# ---------------------------------------------------------------------------
# Cleanup trap — called on ERR / INT / TERM and at normal exit
# ---------------------------------------------------------------------------
_cleanup() {
    local exit_code=${1:-$?}
    if [[ -f "$REPO_ROOT/.run.pid" ]]; then
        echo "[e2e] Stopping backend..."
        bash "$SCRIPT_DIR/run.sh" --stop || true
    fi
    # Preserve the e2e log file for post-hoc investigation; it's cleaned up at
    # the start of the NEXT run (see Phase 2). This lets us inspect tracebacks
    # of failed runs without racing against the cleanup.
    if [[ -n "${E2E_LOG_FILE:-}" && -f "$E2E_LOG_FILE" ]]; then
        echo "[e2e] Log preserved at: $E2E_LOG_FILE"
    fi
    rm -f "$REPO_ROOT/.run.logfile"
    exit "$exit_code"
}
trap '_cleanup $?' EXIT
trap 'bash "$SCRIPT_DIR/run.sh" --stop || true; exit 1' ERR INT TERM

# ---------------------------------------------------------------------------
# Phase status tracking
# ---------------------------------------------------------------------------
P1_STATUS="SKIP"
P1_5_STATUS="SKIP"
P2_STATUS="SKIP"
P3_STATUS="SKIP"
P4_STATUS="SKIP"
P5_STATUS="SKIP"
OVERALL_PASS=true
TTS_SKIPPED=false
PYTEST_MARK_EXPR="e2e"

# ---------------------------------------------------------------------------
# Helpers: read YAML fields (same pattern as run.sh)
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

SERVICES_YML=$(_resolve_services_yml "$YAML_FILE")

if [[ -z "$SERVICES_YML" || ! -f "$SERVICES_YML" ]]; then
    echo "[e2e] FAILED: Could not resolve services config from $YAML_FILE" >&2
    exit 1
fi

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

_read_tts_base_url() {
    local yml="$1"
    if [[ -f "$yml" ]]; then
        grep -E '^\s+base_url:' "$yml" | sed 's/.*base_url:[[:space:]]*//' | tr -d '"' | head -1
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

_print_summary() {
    echo ""
    echo "=== e2e Summary ==="
    printf "  %-14s %s\n" "Phase 1"   "$P1_STATUS"
    printf "  %-14s %s\n" "Phase 1.5" "$P1_5_STATUS"
    printf "  %-14s %s\n" "Phase 2"   "$P2_STATUS"
    printf "  %-14s %s\n" "Phase 3"   "$P3_STATUS"
    printf "  %-14s %s\n" "Phase 4"   "$P4_STATUS"
    printf "  %-14s %s\n" "Phase 5"   "$P5_STATUS"
}

_print_start_hint() {
    local service_name="$1"
    local endpoint="$2"
    local helper_script="$3"

    echo "[e2e] FAILED: ${service_name} not reachable (${endpoint})" >&2
    echo "[e2e] Start it with: bash ${helper_script}" >&2
}

# ---------------------------------------------------------------------------
# Phase 1: Check MongoDB + Qdrant + Neo4j
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 1: External Service Checks ==="
P1_STATUS="FAIL"

MONGO_URI=$(_read_mongo_uri "$SERVICES_YML")
QDRANT_URL=$(_read_qdrant_url "$SERVICES_YML")
NEO4J_URL=$(_read_neo4j_url "$SERVICES_YML")

MONGO_OK=true
QDRANT_OK=true
NEO4J_OK=true

if [[ -n "$MONGO_URI" ]]; then
    HOSTPORT=$(_parse_host_port_from_mongo_uri "$MONGO_URI")
    HOST="${HOSTPORT%%:*}"
    PORT_NUM="${HOSTPORT##*:}"
    PORT_NUM="${PORT_NUM%%/*}"
    MONGO_URI_SAFE=$(echo "$MONGO_URI" | sed 's|://[^@]*@|://***@|')
    if nc -z -w2 "$HOST" "$PORT_NUM" 2>/dev/null; then
        echo "[e2e] MongoDB OK ($MONGO_URI_SAFE)"
    else
        _print_start_hint "MongoDB" "$MONGO_URI_SAFE" "scripts/test_dbs/run_mongodb.sh"
        MONGO_OK=false
    fi
else
    echo "[e2e] FAILED: Could not read MongoDB URI from $SERVICES_YML" >&2
    MONGO_OK=false
fi

if [[ -n "$QDRANT_URL" ]]; then
    HOSTPORT=$(_parse_host_port_from_url "$QDRANT_URL" "6333")
    HOST="${HOSTPORT%%:*}"
    PORT_NUM="${HOSTPORT##*:}"
    if nc -z -w2 "$HOST" "$PORT_NUM" 2>/dev/null; then
        echo "[e2e] Qdrant OK ($QDRANT_URL)"
    else
        _print_start_hint "Qdrant" "$QDRANT_URL" "scripts/test_dbs/run_qdrant.sh"
        QDRANT_OK=false
    fi
else
    echo "[e2e] FAILED: Could not read Qdrant URL from $SERVICES_YML" >&2
    QDRANT_OK=false
fi

if [[ -n "$NEO4J_URL" ]]; then
    HOSTPORT=$(_parse_host_port_from_url "$NEO4J_URL" "7687")
    HOST="${HOSTPORT%%:*}"
    PORT_NUM="${HOSTPORT##*:}"
    if nc -z -w2 "$HOST" "$PORT_NUM" 2>/dev/null; then
        echo "[e2e] Neo4j OK ($NEO4J_URL)"
    else
        _print_start_hint "Neo4j" "$NEO4J_URL" "scripts/test_dbs/run_neo4j.sh"
        NEO4J_OK=false
    fi
else
    echo "[e2e] FAILED: Could not read Neo4j URL from $SERVICES_YML" >&2
    NEO4J_OK=false
fi

if $MONGO_OK && $QDRANT_OK && $NEO4J_OK; then
    P1_STATUS="OK"
    echo "[e2e] Phase 1: PASSED"
else
    OVERALL_PASS=false
    echo "[e2e] Phase 1: FAILED — required services not running"
    _print_summary
    echo ""
    echo "-> e2e: FAILED"
    exit 1
fi

# ---------------------------------------------------------------------------
# Phase 1.5: TTS server check (optional)
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 1.5: TTS Server Check (optional) ==="

TTS_BASE_URL=$(_read_tts_base_url "$SERVICES_YML")
if [[ -n "$TTS_BASE_URL" ]]; then
    # Parse host:port from base_url (e.g. http://localhost:8091)
    TTS_HOSTPORT=$(_parse_host_port_from_url "$TTS_BASE_URL" "80")
    TTS_HOST="${TTS_HOSTPORT%%:*}"
    TTS_PORT="${TTS_HOSTPORT##*:}"
    if nc -z -w2 "$TTS_HOST" "$TTS_PORT" 2>/dev/null; then
        echo "[e2e] TTS server OK ($TTS_BASE_URL)"
        P1_5_STATUS="OK"
    else
        echo "[e2e] WARNING: TTS server not reachable ($TTS_BASE_URL) — TTS tests will be skipped"
        P1_5_STATUS="WARN (TTS server not running)"
        TTS_SKIPPED=true
        PYTEST_MARK_EXPR="e2e and not requires_tts"
    fi
else
    echo "[e2e] WARNING: Could not read TTS base_url from yaml — TTS tests will be skipped"
    P1_5_STATUS="WARN (TTS url not configured)"
    TTS_SKIPPED=true
    PYTEST_MARK_EXPR="e2e and not requires_tts"
fi

# ---------------------------------------------------------------------------
# Phase 2: Start backend on random port 7000-8999
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 2: Start Backend ==="
P2_STATUS="FAIL"

RAND_PORT=$(( 7000 + RANDOM % 2000 ))
echo "[e2e] Using port $RAND_PORT"

# Isolated log file per e2e run — avoids cross-run contamination from shared daily log
TMP_LOG_DIR="$REPO_ROOT/tmp"
mkdir -p "$TMP_LOG_DIR"
# Clean stale e2e logs from prior runs (kept until next run starts, per _cleanup policy)
# Keeping the pattern broad covers both today's and older-date logs.
find "$TMP_LOG_DIR" -maxdepth 1 -name "e2e_*.log" -type f -delete 2>/dev/null || true
export E2E_LOG_FILE="$TMP_LOG_DIR/e2e_$(date +%Y-%m-%d)_${RAND_PORT}.log"
echo "[e2e] Log file: $E2E_LOG_FILE (preserved on exit; cleaned at next run start)"

export BACKEND_PORT="$RAND_PORT"
export SKIP_SERVICE_CHECKS="true"
bash "$SCRIPT_DIR/run.sh" --bg

# Read PID from .run.pid (written by run.sh)
PID_FILE="$REPO_ROOT/.run.pid"
if [[ ! -f "$PID_FILE" ]]; then
    echo "[e2e] FAILED: .run.pid not found after run.sh --bg" >&2
    OVERALL_PASS=false
else
    BACKEND_PID=$(cat "$PID_FILE")
    echo "[e2e] Backend PID: $BACKEND_PID"
    P2_STATUS="OK"
    echo "[e2e] Phase 2: PASSED"
fi

if [[ "$P2_STATUS" == "FAIL" ]]; then
    OVERALL_PASS=false
    _print_summary
    echo ""
    echo "-> e2e: FAILED"
    exit 1
fi

# ---------------------------------------------------------------------------
# Phase 3: Health wait (30s) — kill -0 PID + curl /health
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 3: Health Wait (up to 30s) ==="
P3_STATUS="FAIL"

HEALTH_OK=false
for i in $(seq 1 30); do
    # Check process still alive
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[e2e] FAILED: Backend process $BACKEND_PID died after ${i}s" >&2
        OVERALL_PASS=false
        P3_STATUS="FAIL (process died)"
        break
    fi
    # Check HTTP health
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://127.0.0.1:${RAND_PORT}/health" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        HEALTH_OK=true
        echo "[e2e] Health OK (HTTP 200) after ${i}s"
        break
    fi
    sleep 1
done

if $HEALTH_OK; then
    P3_STATUS="OK"
    echo "[e2e] Phase 3: PASSED"
else
    if [[ "$P3_STATUS" == "FAIL (process died)" ]]; then
        : # Already set above (process died)
    else
        OVERALL_PASS=false
        P3_STATUS="FAIL (no HTTP 200 in 30s)"
    fi
    echo "[e2e] Phase 3: FAILED"
fi

# ---------------------------------------------------------------------------
# Phase 4: Run examples
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 4: Run Examples ==="
P4_STATUS="FAIL"

BASE_URL="http://127.0.0.1:${RAND_PORT}"

# Read the isolated log file path written by run.sh
LOGFILE_PTR="$REPO_ROOT/.run.logfile"
LOG_FILE=""
if [[ -f "$LOGFILE_PTR" ]]; then
    LOG_FILE=$(cat "$LOGFILE_PTR")
fi

if [[ "$P3_STATUS" != "OK" ]]; then
    echo "[e2e] Skipping examples — backend not healthy"
    P4_STATUS="SKIP (backend not healthy)"
else
    echo "[e2e] Running pytest -m $PYTEST_MARK_EXPR..."
    if BACKEND_URL="$BASE_URL" FASTAPI_URL="$BASE_URL" uv run pytest -m "$PYTEST_MARK_EXPR" --tb=long -v; then
        P4_STATUS="OK"
        echo "[e2e] Phase 4: PASSED"
    else
        OVERALL_PASS=false
        P4_STATUS="FAIL"
        echo "[e2e] Phase 4: FAILED"
    fi
fi

# ---------------------------------------------------------------------------
# Phase 5: Log ERROR check
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 5: Log ERROR Check ==="
P5_STATUS="SKIP"

if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
    ERROR_LINES=$(grep -E '\|\s+ERROR\s+\|' "$LOG_FILE" 2>/dev/null | grep -v 'uvicorn\.error' || true)
    ERROR_COUNT=$(echo "$ERROR_LINES" | grep -c . || true)
    if [[ "$ERROR_COUNT" -gt 0 ]]; then
        echo "[e2e] Found $ERROR_COUNT app ERROR line(s):"
        echo "$ERROR_LINES"
        OVERALL_PASS=false
        P5_STATUS="FAIL (${ERROR_COUNT} app ERROR lines)"
        echo "[e2e] Phase 5: FAILED"
    else
        P5_STATUS="OK"
        echo "[e2e] Phase 5: PASSED (no app ERROR lines)"
    fi
else
    echo "[e2e] WARNING: Log file not found — skipping ERROR check"
    P5_STATUS="SKIP (log file not found)"
fi

# ---------------------------------------------------------------------------
# Phase 6: Cleanup (log deletion handled by _cleanup EXIT trap)
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 6: Cleanup ==="
bash "$SCRIPT_DIR/run.sh" --stop || true
# Remove .run.pid so EXIT trap won't double-stop
rm -f "$REPO_ROOT/.run.pid"
echo "[e2e] Phase 6: Done"

# ---------------------------------------------------------------------------
# Phase 7: Summary
# ---------------------------------------------------------------------------
_print_summary

echo ""
if $OVERALL_PASS; then
    echo "-> e2e: PASSED"
    exit 0
else
    echo "-> e2e: FAILED"
    exit 1
fi
