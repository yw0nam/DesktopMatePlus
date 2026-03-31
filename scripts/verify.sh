#!/usr/bin/env bash
# verify.sh — verification harness for the backend app
#
# Usage:
#   scripts/verify.sh            — full verification (health + examples + logs)
#   scripts/verify.sh --health   — health check only
#   scripts/verify.sh --examples — examples only
#   scripts/verify.sh --logs     — log clean check only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Determine which checks to run
RUN_HEALTH=false
RUN_EXAMPLES=false
RUN_LOGS=false

case "${1:-all}" in
    --health)   RUN_HEALTH=true ;;
    --examples) RUN_EXAMPLES=true ;;
    --logs)     RUN_LOGS=true ;;
    *)          RUN_HEALTH=true; RUN_EXAMPLES=true; RUN_LOGS=true ;;
esac

# Record verify start time for log clean check
VERIFY_START_TIME=$(date +%H:%M:%S)

# Get port
PORT=$(bash "$SCRIPT_DIR/run.sh" --port)

# Result tracking
HEALTH_STATUS="SKIP"
STM_STATUS="SKIP"
TTS_STATUS="SKIP"
LOGS_STATUS="SKIP"
OVERALL_PASS=true

# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
if $RUN_HEALTH; then
    echo "[verify] Checking health at http://localhost:${PORT}/health ..."
    HEALTH_STATUS="FAIL"
    MAX_RETRY=30
    for i in $(seq 1 $MAX_RETRY); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            HEALTH_STATUS="OK"
            break
        fi
        echo "[verify]   retry $i/$MAX_RETRY (got $HTTP_CODE)..."
        sleep 1
    done
    if [[ "$HEALTH_STATUS" != "OK" ]]; then
        OVERALL_PASS=false
    fi
fi

# ---------------------------------------------------------------------------
# 2. Examples
# ---------------------------------------------------------------------------
if $RUN_EXAMPLES; then
    echo "[verify] Running stm_api_demo.py ..."
    STM_STATUS="FAIL"
    if uv run python examples/stm_api_demo.py 2>&1; then
        STM_STATUS="OK"
    else
        OVERALL_PASS=false
    fi

    echo "[verify] Running realtime_tts_streaming_demo.py ..."
    TTS_STATUS="FAIL"
    if uv run python examples/realtime_tts_streaming_demo.py 2>&1; then
        TTS_STATUS="OK"
    else
        OVERALL_PASS=false
    fi
fi

# ---------------------------------------------------------------------------
# 3. Log clean check
# ---------------------------------------------------------------------------
if $RUN_LOGS; then
    echo "[verify] Checking logs for ERROR/CRITICAL since $VERIFY_START_TIME ..."
    LOGS_STATUS="OK"

    # Count errors since verify start
    ERROR_COUNT=$(bash "$SCRIPT_DIR/logs.sh" --level ERROR --since "$VERIFY_START_TIME" 2>/dev/null | wc -l || echo "0")
    ERROR_COUNT=$(echo "$ERROR_COUNT" | tr -d '[:space:]')

    if [[ "$ERROR_COUNT" -gt 0 ]]; then
        LOGS_STATUS="${ERROR_COUNT} ERRORs found"
        OVERALL_PASS=false
        # Show the errors
        bash "$SCRIPT_DIR/logs.sh" --level ERROR --since "$VERIFY_START_TIME" 2>/dev/null || true
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Verification Summary ==="

if $RUN_HEALTH; then
    [[ "$HEALTH_STATUS" == "OK" ]] && ICON="OK" || ICON="FAIL"
    printf "  %-12s %s\n" "health" "$ICON"
fi

if $RUN_EXAMPLES; then
    [[ "$STM_STATUS" == "OK" ]] && ICON="OK" || ICON="FAIL"
    printf "  %-12s %s\n" "stm_api" "$ICON"

    [[ "$TTS_STATUS" == "OK" ]] && ICON="OK" || ICON="FAIL"
    printf "  %-12s %s\n" "tts_demo" "$ICON"
fi

if $RUN_LOGS; then
    [[ "$LOGS_STATUS" == "OK" ]] && ICON="OK" || ICON="FAIL"
    printf "  %-12s %s\n" "log clean" "$LOGS_STATUS"
fi

echo ""
if $OVERALL_PASS; then
    echo "-> overall: PASSED"
    exit 0
else
    echo "-> overall: FAILED"
    exit 1
fi
