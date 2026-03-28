#!/usr/bin/env bash
# metrics.sh — query /metrics endpoint, parse Prometheus text format
set -euo pipefail

PORT_FILE=".run.port"
DEFAULT_PORT=5500

get_port() {
  if [[ -f "$PORT_FILE" ]]; then cat "$PORT_FILE"; else echo "$DEFAULT_PORT"; fi
}

usage() {
  cat <<'EOF'
Usage: scripts/metrics.sh [OPTIONS]
  --latency [avg|p50|p95|p99]  Show request latency (default: avg)
  --errors                      Show error rate
  --connections                 Show active WebSocket connections
  --all                         Show all metrics summary
  -h, --help                    Show help
EOF
}

METRIC="all"
PERCENTILE="avg"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --latency) METRIC="latency"; PERCENTILE="${2:-avg}"; shift 2 2>/dev/null || shift ;;
    --errors)  METRIC="errors"; shift ;;
    --connections) METRIC="connections"; shift ;;
    --all)     METRIC="all"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown: $1"; usage; exit 1 ;;
  esac
done

PORT="$(get_port)"
BASE_URL="http://localhost:${PORT}"

raw="$(curl -sf "${BASE_URL}/metrics" 2>/dev/null)" || {
  echo "ERROR: Cannot reach ${BASE_URL}/metrics"
  exit 1
}

# Parse and display based on metric type
case "$METRIC" in
  latency)
    echo "=== Request Latency (${PERCENTILE}) ==="
    echo "$raw" | grep "http_request_duration_seconds" | grep -v "^#" | head -20
    ;;
  errors)
    echo "=== Error Rate ==="
    echo "$raw" | grep "http_requests_total" | grep -v "^#" | grep 'status="[45]' | head -20
    ;;
  connections)
    echo "=== Active WebSocket Connections ==="
    echo "$raw" | grep "websocket_active_connections" | grep -v "^#"
    ;;
  all)
    echo "=== Metrics Summary ==="
    echo "--- Requests ---"
    echo "$raw" | grep "http_requests_total" | grep -v "^#" | head -10
    echo "--- Latency ---"
    echo "$raw" | grep "http_request_duration_seconds_count" | grep -v "^#" | head -5
    echo "--- Connections ---"
    echo "$raw" | grep "websocket_active_connections" | grep -v "^#"
    ;;
esac
