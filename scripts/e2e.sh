#!/usr/bin/env bash
# e2e.sh — end-to-end verification pipeline for the backend
#
# Usage:
#   bash scripts/e2e.sh
#
# Prerequisites:
#   - MongoDB running (host/port from yaml_files/services/checkpointer.yml)
#   - Qdrant running (host/port from yaml_files/services/ltm_service/mem0.yml)
#   - TTS server optional (warning + skip if not available)
#
# Phases:
#   Phase 1  : Check MongoDB + Qdrant connectivity
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

# ---------------------------------------------------------------------------
# Cleanup trap — called on ERR / INT / TERM and at normal exit
# ---------------------------------------------------------------------------
_cleanup() {
    local exit_code=${1:-$?}
    if [[ -f "$REPO_ROOT/.run.pid" ]]; then
        echo "[e2e] Stopping backend..."
        bash "$SCRIPT_DIR/run.sh" --stop || true
    fi
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

# ---------------------------------------------------------------------------
# Helpers: read YAML fields (same pattern as run.sh)
# ---------------------------------------------------------------------------
_read_mongo_uri() {
    local yml="$REPO_ROOT/yaml_files/services.e2e.yml"
    if [[ -f "$yml" ]]; then
        grep -E 'connection_string:' "$yml" | sed 's/.*connection_string:[[:space:]]*//' | tr -d '"' | head -1
    fi
}

_read_qdrant_url() {
    local yml="$REPO_ROOT/yaml_files/services.e2e.yml"
    if [[ -f "$yml" ]]; then
        grep -A5 'provider: "qdrant"' "$yml" | grep -E '^\s+url:' | sed 's/.*url:[[:space:]]*//' | tr -d '"' | head -1
    fi
}

_read_tts_base_url() {
    local yml="$REPO_ROOT/yaml_files/services.e2e.yml"
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
    echo "${host}:${port}"
}

# ---------------------------------------------------------------------------
# Phase 1: Check MongoDB + Qdrant
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 1: External Service Checks ==="
P1_STATUS="FAIL"

MONGO_URI=$(_read_mongo_uri)
QDRANT_URL=$(_read_qdrant_url)

MONGO_OK=true
QDRANT_OK=true

if [[ -n "$MONGO_URI" ]]; then
    HOSTPORT=$(_parse_host_port_from_mongo_uri "$MONGO_URI")
    HOST="${HOSTPORT%%:*}"
    PORT_NUM="${HOSTPORT##*:}"
    PORT_NUM="${PORT_NUM%%/*}"
    MONGO_URI_SAFE=$(echo "$MONGO_URI" | sed 's|://[^@]*@|://***@|')
    if nc -z -w2 "$HOST" "$PORT_NUM" 2>/dev/null; then
        echo "[e2e] MongoDB OK ($MONGO_URI_SAFE)"
    else
        echo "[e2e] FAILED: MongoDB not reachable ($MONGO_URI_SAFE)" >&2
        MONGO_OK=false
    fi
else
    echo "[e2e] WARNING: Could not read MongoDB URI from yaml — skipping check"
fi

if [[ -n "$QDRANT_URL" ]]; then
    HOSTPORT=$(_parse_host_port_from_url "$QDRANT_URL")
    HOST="${HOSTPORT%%:*}"
    PORT_NUM="${HOSTPORT##*:}"
    if nc -z -w2 "$HOST" "$PORT_NUM" 2>/dev/null; then
        echo "[e2e] Qdrant OK ($QDRANT_URL)"
    else
        echo "[e2e] FAILED: Qdrant not reachable ($QDRANT_URL)" >&2
        QDRANT_OK=false
    fi
else
    echo "[e2e] WARNING: Could not read Qdrant URL from yaml — skipping check"
fi

if $MONGO_OK && $QDRANT_OK; then
    P1_STATUS="OK"
    echo "[e2e] Phase 1: PASSED"
else
    OVERALL_PASS=false
    echo "[e2e] Phase 1: FAILED — required services not running"
    # Exit early: no point starting backend without required services
    echo ""
    echo "=== e2e Summary ==="
    printf "  %-14s %s\n" "Phase 1"   "$P1_STATUS"
    printf "  %-14s %s\n" "Phase 1.5" "$P1_5_STATUS"
    printf "  %-14s %s\n" "Phase 2"   "$P2_STATUS"
    printf "  %-14s %s\n" "Phase 3"   "$P3_STATUS"
    printf "  %-14s %s\n" "Phase 4"   "$P4_STATUS"
    printf "  %-14s %s\n" "Phase 5"   "$P5_STATUS"
    echo ""
    echo "-> e2e: FAILED"
    exit 1
fi

# ---------------------------------------------------------------------------
# Phase 1.5: TTS server check (optional)
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 1.5: TTS Server Check (optional) ==="

TTS_BASE_URL=$(_read_tts_base_url)
if [[ -n "$TTS_BASE_URL" ]]; then
    # Parse host:port from base_url (e.g. http://localhost:8091)
    TTS_HOST=$(echo "$TTS_BASE_URL" | sed -E 's|https?://([^:/]+).*|\1|')
    TTS_PORT=$(echo "$TTS_BASE_URL" | sed -E 's|https?://[^:]+:([0-9]+).*|\1|')
    if [[ "$TTS_PORT" == "$TTS_BASE_URL" ]]; then
        TTS_PORT=80
    fi
    if nc -z -w2 "$TTS_HOST" "$TTS_PORT" 2>/dev/null; then
        echo "[e2e] TTS server OK ($TTS_BASE_URL)"
        P1_5_STATUS="OK"
    else
        echo "[e2e] WARNING: TTS server not reachable ($TTS_BASE_URL) — TTS tests will be skipped"
        P1_5_STATUS="WARN (TTS server not running)"
        TTS_SKIPPED=true
    fi
else
    echo "[e2e] WARNING: Could not read TTS base_url from yaml — TTS tests will be skipped"
    P1_5_STATUS="WARN (TTS url not configured)"
    TTS_SKIPPED=true
fi

export YAML_FILE="yaml_files/e2e.yml"

# ---------------------------------------------------------------------------
# Phase 2: Start backend on random port 7000-8999
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 2: Start Backend ==="
P2_STATUS="FAIL"

# Delete ALL stale log files so Phase 5 only sees errors from this run
_LOGDIR_PRE="$REPO_ROOT/.run.logdir"
if [[ -f "$_LOGDIR_PRE" ]]; then
    _LOG_DIR="$(cat "$_LOGDIR_PRE")"
    [[ -n "$_LOG_DIR" ]] && rm -f "$_LOG_DIR"/app_*.log 2>/dev/null || true
fi

RAND_PORT=$(( 7000 + RANDOM % 2000 ))
echo "[e2e] Using port $RAND_PORT"

export BACKEND_PORT="$RAND_PORT"
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
    echo ""
    echo "=== e2e Summary ==="
    printf "  %-14s %s\n" "Phase 1"   "$P1_STATUS"
    printf "  %-14s %s\n" "Phase 1.5" "$P1_5_STATUS"
    printf "  %-14s %s\n" "Phase 2"   "$P2_STATUS"
    printf "  %-14s %s\n" "Phase 3"   "$P3_STATUS"
    printf "  %-14s %s\n" "Phase 4"   "$P4_STATUS"
    printf "  %-14s %s\n" "Phase 5"   "$P5_STATUS"
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

# Read LOG_DIR from .run.logdir (written by run.sh)
LOGDIR_FILE="$REPO_ROOT/.run.logdir"
LOG_FILE=""
if [[ -f "$LOGDIR_FILE" ]]; then
    LOG_DIR_PATH=$(cat "$LOGDIR_FILE")
    LOG_FILE="$LOG_DIR_PATH/app_$(date +%Y-%m-%d).log"
fi

if [[ "$P3_STATUS" != "OK" ]]; then
    echo "[e2e] Skipping examples — backend not healthy"
    P4_STATUS="SKIP (backend not healthy)"
else
    echo "[e2e] Running pytest -m e2e..."
    if BACKEND_URL="$BASE_URL" FASTAPI_URL="$BASE_URL" uv run pytest -m e2e --tb=long -v; then
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
# Phase 6: Cleanup (handled by EXIT trap)
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 6: Cleanup ==="
bash "$SCRIPT_DIR/run.sh" --stop || true
# Remove .run.pid so EXIT trap won't double-stop
rm -f "$REPO_ROOT/.run.pid"
# Remove e2e log file — test logs should not accumulate
if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
    rm -f "$LOG_FILE"
fi
echo "[e2e] Phase 6: Done"

# ---------------------------------------------------------------------------
# Phase 7: Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== e2e Summary ==="
printf "  %-14s %s\n" "Phase 1"   "$P1_STATUS"
printf "  %-14s %s\n" "Phase 1.5" "$P1_5_STATUS"
printf "  %-14s %s\n" "Phase 2"   "$P2_STATUS"
printf "  %-14s %s\n" "Phase 3"   "$P3_STATUS"
printf "  %-14s %s\n" "Phase 4"   "$P4_STATUS"
printf "  %-14s %s\n" "Phase 5"   "$P5_STATUS"

echo ""
if $OVERALL_PASS; then
    echo "-> e2e: PASSED"
    exit 0
else
    echo "-> e2e: FAILED"
    exit 1
fi
