# Logging Guide

Updated: 2025-12-10

## 1. Synopsis

- **Purpose**: Unified logging standard for DesktopMate+ Backend with Request ID tracking, human-readable format, and automated rotation
- **I/O**: Logger configuration → Consistent, traceable log entries across all services

## 2. Core Logic

### Format Standard

```
[HH:mm:ss.SSS] | LEVEL    | module:line | [RequestID] - message
```

**Example:**
```text
11:29:24.548 | INFO     | handlers:551 | [req_x9z1] - Sent turn_end event to connection 4074d
11:33:01.364 | INFO     | websocket:64 | [req_x9z1] - ⚡ WebSocket disconnected: 4074d
```

### Log Levels

| Level | Use Case | Production |
|-------|----------|------------|
| **ERROR** | System failures (DB connection lost, API timeout) | ✓ |
| **WARN** | Recoverable issues (retry triggered, deprecated API) | ✓ |
| **INFO** | Business flow (API calls, state changes, sessions) | ✓ |
| **DEBUG** | Diagnostic data (payloads, queries) | ✗ |

### Request ID Tracking

Generate unique ID at entry point and bind to logger:

```python
from loguru import logger
import uuid

# At API entry
request_id = f"req_{uuid.uuid4().hex[:8]}"
context_logger = logger.bind(request_id=request_id)

# Use throughout request
context_logger.info("Processing chat message")
```

### API Logging Patterns

**HTTP Entry/Exit:**
```python
logger.info(f"➡️ POST /api/chat/start")
logger.info(f"⬅️ POST /api/chat/start (200 OK) - 150ms")
```

**WebSocket Events:**
```python
logger.info(f"🔌 WebSocket connected: {connection_id}")
logger.info(f"⚡ WebSocket disconnected: {connection_id}")
logger.info(f"💬 Message received from {connection_id}: {msg_type}")
```

### Configuration

Edit `src/core/logger.py`:

```python
from loguru import logger

logger.remove()

log_format = (
    "<green>{time:HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
    "<magenta>[{extra[request_id]}]</magenta> - "
    "<level>{message}</level>"
)

# Console (development)
logger.add(sys.stderr, format=log_format, level="DEBUG")

# File (daily rotation)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    format=log_format,
    level="INFO"
)
```

### Constraints

- **Never log sensitive data** (passwords, tokens, PII)
- **Production level**: INFO and above only
- **Request ID required** for all API/WebSocket logs
- **Use emoji markers** for visibility (➡️ ⬅️ 🔌 ⚡ 💬)

## 3. Usage

### Basic Logging

```python
from loguru import logger

# Service operations
logger.info(f"Agent initialized: {agent_type}")
logger.info(f"Processing message for session {session_id}")
logger.info(f"Tool call detected: '{tool_name}'")

# Memory operations
logger.info(f"Adding memory: user={user_id}, type={mem_type}")
logger.info(f"Found {len(results)} memories")

# TTS operations
logger.info(f"TTS synthesis started: text_length={len(text)}")
logger.info(f"TTS completed: duration={audio_duration}s")

# Errors
logger.error(f"Error searching memory: {e}")
```

### With Request ID (FastAPI Middleware)

```python
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = f"req_{uuid.uuid4().hex[:8]}"

        with logger.contextualize(request_id=request_id):
            response = await call_next(request)

        return response
```

### Debugging Logs

```bash
# View today's logs
tail -f logs/app_$(date +%Y-%m-%d).log

# Trace specific request
grep "req_x9z1" logs/app_*.log

# Find all errors
grep "ERROR" logs/app_*.log
```

---

## Appendix

### A. Service-Specific Patterns

**Agent Service:**
```python
logger.info(f"Agent initialized: {agent_type}")
logger.info(f"Processing message for session {session_id}")
logger.debug(f"Message payload: {messages}")
logger.info(f"Tool call detected: '{tool_name}'")
logger.info(f"Message processing completed. Chunks: {chunk_count}")
```

**STM/LTM Service:**
```python
logger.info(f"Adding memory: user={user_id}, type={mem_type}")
logger.info(f"Searching memories: query='{query}', limit={limit}")
logger.info(f"Memory deleted: id={memory_id}")
logger.debug(f"Memory content: {memory_data}")
```

**TTS Service:**
```python
logger.info(f"TTS synthesis started: text_length={len(text)}")
logger.debug(f"Streaming audio chunk: {chunk_size} bytes")
logger.info(f"TTS completed: duration={audio_duration}s")
```

**VLM Service:**
```python
logger.info(f"VLM analysis started: image_size={image.size}")
logger.info(f"Detected {len(objects)} objects")
logger.debug(f"Detection details: {objects}")
```

### B. Best Practices

**✅ DO:**
- Use Request ID for all logs within request context
- Log API entry/exit points with clear markers
- Include context (session_id, user_id, connection_id)
- Keep messages concise and informative
- Log errors with exception details

**❌ DON'T:**
- Log sensitive data (passwords, tokens, personal info)
- Use JSON format for human-readable files
- Include full file paths in logs
- Log in tight loops without throttling
- Use `print()` statements instead of logger
- Leave DEBUG logs in production code

**Good Example:**
```python
logger.info(f"Chat session started: session_id={session_id}, user_id={user_id}")
logger.info(f"Processing turn {turn_number} for connection {conn_id}")
```

**Bad Example:**
```python
logger.info("starting the chat processing now...")
logger.info(f"Full message object: {entire_message_dump}")
```

### C. Environment Configuration

```python
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_RETENTION = os.getenv("LOG_RETENTION", "30 days")
LOG_DIR = os.getenv("LOG_DIR", "logs")
```

### D. File Rotation Details

**Naming Convention:**
```
logs/
├── app_2025-12-10.log
├── app_2025-12-11.log
└── app_2025-12-12.log
```

**Retention Policy:**
- Development: 7 days
- Production: 30 days
- Automatic cleanup after retention period

### E. Related Documents

- `docs/guidelines/DOCUMENT_GUIDE.md` - Documentation standards
- `rule.md` - Backend development guidelines
- `src/core/logger.py` - Logger implementation
