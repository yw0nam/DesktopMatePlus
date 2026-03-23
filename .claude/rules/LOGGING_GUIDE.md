---
paths:
  - "src/**/*.py"
---

# Logging Guide

Updated: 2026-03-23

## 1. Synopsis

- **Purpose**: Unified logging standard with Request ID tracking, human-readable format, and daily rotation
- **I/O**: Logger config (`src/core/logger.py`) → consistent, traceable entries across all services

## 2. Core Logic

### Format

```
[HH:mm:ss.SSS] | LEVEL    | module:line | [RequestID] - message
```

Example:
```
11:29:24.548 | INFO     | handlers:551 | [req_x9z1] - Sent turn_end event to connection 4074d
```

### Log Levels

| Level | Use Case | Production |
|-------|----------|------------|
| **ERROR** | System failures (DB down, API timeout) | ✓ |
| **WARN** | Recoverable issues (retry, deprecated API) | ✓ |
| **INFO** | Business flow (calls, state changes, sessions) | ✓ |
| **DEBUG** | Diagnostic data (payloads, queries) | ✗ |

### Request ID Tracking

Bind at entry point, use throughout:

```python
request_id = f"req_{uuid.uuid4().hex[:8]}"
with logger.contextualize(request_id=request_id):
    response = await call_next(request)
```

### Emoji Markers

```python
logger.info(f"➡️ POST /api/chat/start")
logger.info(f"⬅️ POST /api/chat/start (200 OK)")
logger.info(f"🔌 WebSocket connected: {connection_id}")
logger.info(f"⚡ WebSocket disconnected: {connection_id}")
logger.info(f"💬 Message received from {connection_id}: {msg_type}")
```

### Constraints

- **Never** log sensitive data (passwords, tokens, PII)
- **Never** use `print()` — always `logger`
- **Never** leave DEBUG logs in production code
- Request ID required for all API/WebSocket logs
- Keep messages concise with context (`session_id`, `user_id`, `connection_id`)

## 3. Usage

```python
from loguru import logger

logger.info(f"Agent initialized: {agent_type}")
logger.info(f"Processing message for session {session_id}")
logger.info(f"Tool call detected: '{tool_name}'")
logger.info(f"TTS synthesis started: text_length={len(text)}")
logger.error(f"Error searching memory: {e}")
```

---

## Appendix

### A. Logger Configuration (`src/core/logger.py`)

```python
logger.remove()
log_format = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
    "<magenta>[{extra[request_id]}]</magenta> - <level>{message}</level>"
)
logger.add(sys.stderr, format=log_format, level="DEBUG")
logger.add("logs/app_{time:YYYY-MM-DD}.log", rotation="00:00", retention="30 days", format=log_format, level="INFO")
```

### B. PatchNote

2026-03-23: Trimmed Appendix — removed redundant service-specific examples and best-practices table; consolidated into core constraints.
