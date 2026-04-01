#!/usr/bin/env bash
# check-task.sh — three-phase task verification harness
#
# Usage:
#   scripts/check-task.sh -k <keyword>   Run all phases with pytest keyword filter
#
# Phases:
#   Phase 1: Lint (ruff + black + structural tests)
#   Phase 2: pytest -k <keyword>
#   Phase 3: Start backend on random port → health wait → TTS demo E2E → log ERROR check → stop

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
KEYWORD=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -k)
            KEYWORD="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 -k <keyword>" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$KEYWORD" ]]; then
    echo "Error: -k <keyword> is required" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PHASE1_STATUS="SKIP"
PHASE2_STATUS="SKIP"
PHASE3_STATUS="SKIP"
OVERALL_PASS=true
BACKEND_PID=""

cleanup() {
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[check-task] Stopping backend (PID $BACKEND_PID)..."
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
        echo "[check-task] Backend stopped."
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Phase 1: Lint
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 1: Lint ==="
PHASE1_STATUS="FAIL"
if sh "$SCRIPT_DIR/lint.sh"; then
    PHASE1_STATUS="OK"
    echo "[check-task] Phase 1: PASSED"
else
    OVERALL_PASS=false
    echo "[check-task] Phase 1: FAILED"
fi

# ---------------------------------------------------------------------------
# Phase 2: pytest -k <keyword>
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 2: pytest -k '$KEYWORD' ==="
PHASE2_STATUS="FAIL"
# test_fish_speech.py is excluded: fish_speech module was removed but the test file
# was not deleted. Skip it to prevent collection errors from blocking other tests.
if uv run pytest -k "$KEYWORD" -v --ignore=tests/services/test_fish_speech.py; then
    PHASE2_STATUS="OK"
    echo "[check-task] Phase 2: PASSED"
else
    OVERALL_PASS=false
    echo "[check-task] Phase 2: FAILED"
fi

# ---------------------------------------------------------------------------
# Phase 3: E2E — backend start → health → TTS demo → log check → stop
# ---------------------------------------------------------------------------
echo ""
echo "=== Phase 3: E2E ==="

# Pick a random port in 5000-9999
RAND_PORT=$(( 5000 + RANDOM % 5000 ))
echo "[check-task] Using port $RAND_PORT for backend"

# Prepare log dir
LOG_DIR="$REPO_ROOT/logs/check-task-$$"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/app.log"

# Start backend in background (skip external service checks by using --no-reload to fail fast)
E2E_START=$(date +%H:%M:%S)
echo "[check-task] Starting backend on port $RAND_PORT..."
LOG_DIR="$LOG_DIR" uv run uvicorn src.main:app --port "$RAND_PORT" --host 127.0.0.1 \
    >> "$LOG_FILE" 2>&1 &
BACKEND_PID=$!

# Wait for health — up to 30s
echo "[check-task] Waiting for health (up to 30s)..."
HEALTH_OK=false
for i in $(seq 1 30); do
    # Accept any HTTP response (even 500) as "server started" — external services may be unavailable
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${RAND_PORT}/health" 2>/dev/null; true)
    if [[ "$HTTP_CODE" =~ ^[0-9]{3}$ && "$HTTP_CODE" != "000" ]]; then
        HEALTH_OK=true
        echo "[check-task] Backend responding (HTTP ${HTTP_CODE}) after ${i}s"
        break
    fi
    sleep 1
done

if ! $HEALTH_OK; then
    echo "[check-task] Backend did not start (no TCP response) in 30s" >&2
    OVERALL_PASS=false
    PHASE3_STATUS="FAIL (backend not started)"
else
    # Run TTS streaming demo
    echo "[check-task] Running realtime_tts_streaming_demo.py..."
    DEMO_STATUS="FAIL"
    if uv run python examples/realtime_tts_streaming_demo.py \
        --ws-url "ws://127.0.0.1:${RAND_PORT}/v1/chat/stream" \
        >> "$LOG_FILE" 2>&1; then
        DEMO_STATUS="OK"
    else
        OVERALL_PASS=false
        echo "[check-task] Demo script returned non-zero exit code"
    fi

    # Check logs for application-level ERRORs (loguru format: "| ERROR    |")
    # Excludes uvicorn infrastructure lines like "ERROR:    Exception in ASGI application"
    echo "[check-task] Checking logs for app ERRORs since $E2E_START..."
    ERROR_LINES=$(grep -E '\|\s+ERROR\s+\|' "$LOG_FILE" 2>/dev/null || true)
    ERROR_COUNT=$(echo "$ERROR_LINES" | grep -c . || true)

    if [[ "$DEMO_STATUS" == "FAIL" ]]; then
        PHASE3_STATUS="FAIL (demo exited non-zero)"
    elif [[ "$ERROR_COUNT" -gt 0 ]]; then
        echo "[check-task] Found $ERROR_COUNT ERROR line(s) in log:"
        echo "$ERROR_LINES"
        OVERALL_PASS=false
        PHASE3_STATUS="FAIL (${ERROR_COUNT} app ERROR lines)"
    else
        PHASE3_STATUS="OK"
    fi
fi

# Stop backend
cleanup
BACKEND_PID=""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== check-task Summary (keyword: '$KEYWORD') ==="
printf "  %-12s %s\n" "Phase 1" "$PHASE1_STATUS"
printf "  %-12s %s\n" "Phase 2" "$PHASE2_STATUS"
printf "  %-12s %s\n" "Phase 3" "$PHASE3_STATUS"
echo ""
if $OVERALL_PASS; then
    echo "-> check-task: PASSED"
    exit 0
else
    echo "-> check-task: FAILED"
    exit 1
fi
