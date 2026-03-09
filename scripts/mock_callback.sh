#!/usr/bin/env bash
# mock_callback.sh — Simulate a NanoClaw callback to the FastAPI backend.
#
# Usage:
#   ./scripts/mock_callback.sh <task_id> <session_id> [done|failed]
#
# Prerequisites:
#   - The FastAPI backend must be running (default: http://localhost:8000).
#   - <task_id> must be a real pending task ID stored in STM for the given
#     session.  You can obtain one by triggering a DelegateTaskTool call and
#     inspecting the logs or STM document for the task_id field.
#   - Override the backend URL with BACKEND_URL env var if needed:
#       BACKEND_URL=http://localhost:9000 ./scripts/mock_callback.sh ...
#
# Examples:
#   ./scripts/mock_callback.sh 550e8400-e29b-41d4-a716-446655440000 session-abc123
#   ./scripts/mock_callback.sh 550e8400-e29b-41d4-a716-446655440000 session-abc123 failed

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <task_id> <session_id> [done|failed]" >&2
    exit 1
fi

TASK_ID="$1"
SESSION_ID="$2"
STATUS="${3:-done}"

if [[ "$STATUS" != "done" && "$STATUS" != "failed" ]]; then
    echo "Error: status must be 'done' or 'failed', got: '$STATUS'" >&2
    exit 1
fi

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
URL="${BACKEND_URL}/v1/callback/nanoclaw/${SESSION_ID}"

PAYLOAD=$(cat <<EOF
{
  "task_id": "${TASK_ID}",
  "status": "${STATUS}",
  "summary": "Mock callback from mock_callback.sh (status=${STATUS})"
}
EOF
)

# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
echo ">>> Sending NanoClaw callback"
echo "    URL    : ${URL}"
echo "    Payload: ${PAYLOAD}"
echo ""

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${URL}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}")

echo "<<< HTTP status: ${HTTP_STATUS}"

if [[ "$HTTP_STATUS" -ge 200 && "$HTTP_STATUS" -lt 300 ]]; then
    echo "    OK — callback accepted by backend."
else
    echo "    WARN — unexpected status code." >&2
    exit 1
fi
