# WebSocket Error Handling

Updated: 2026-03-03

## 1. Synopsis

- **Purpose**: Classify and handle WebSocket errors with appropriate retry strategies
- **I/O**: Exception → Error Severity → Retry Decision + Backoff Delay

## 2. Core Logic

### Error Classification System

All errors are classified into three severity levels:

```python
from src.services.websocket_service.error_classifier import ErrorClassifier, ErrorSeverity

severity = ErrorClassifier.classify(exception)
# Returns: ErrorSeverity.TRANSIENT | RECOVERABLE | FATAL
```

| Severity | Meaning | Strategy | Examples |
|----------|---------|----------|----------|
| **TRANSIENT** | Temporary network issues | Retry immediately, no backoff | TimeoutError, ConnectionResetError |
| **RECOVERABLE** | Parsing/validation issues | Retry after backoff delay | ValidationError, ValueError |
| **FATAL** | Unrecoverable errors | Terminate connection | WebSocketDisconnect, RuntimeError |

### Classification Logic

**Automatic Classification:**

```python
ErrorClassifier.SEVERITY_MAP = {
    # TRANSIENT - retry immediately
    asyncio.TimeoutError: ErrorSeverity.TRANSIENT,
    ConnectionResetError: ErrorSeverity.TRANSIENT,
    ConnectionAbortedError: ErrorSeverity.TRANSIENT,
    BrokenPipeError: ErrorSeverity.TRANSIENT,

    # RECOVERABLE - retry with backoff
    ValidationError: ErrorSeverity.RECOVERABLE,
    ValueError: ErrorSeverity.RECOVERABLE,
    KeyError: ErrorSeverity.RECOVERABLE,

    # FATAL - terminate immediately
    WebSocketDisconnect: ErrorSeverity.FATAL,
    RuntimeError: ErrorSeverity.FATAL,
}
```

Unknown exceptions default to FATAL.

### Retry Decision Algorithm

```python
should_retry = ErrorClassifier.should_retry(
    exc=exception,
    error_count=current_consecutive_errors,
    max_tolerance=5  # from config
)
```

**Rules:**

1. FATAL errors never retry
2. Error count exceeds max_tolerance → stop
3. TRANSIENT/RECOVERABLE within tolerance → retry

### Backoff Strategy

```python
delay = ErrorClassifier.get_backoff_delay(
    exc=exception,
    base_delay=0.5  # from config
)
```

**Delays:**

- TRANSIENT: 0s (immediate retry)
- RECOVERABLE: base_delay (0.5s default)
- FATAL: 0s (no retry, immediate closure)

### Error Handling Flow

```text
[Exception Occurs]
        ↓
    Classify ────→ FATAL? ───Yes──→ [Close Connection]
        ↓
       No
        ↓
 Check Error Count ──→ Exceeded? ─Yes─→ [Close Connection]
        ↓
       No
        ↓
  Get Backoff Delay
        ↓
   Apply Delay
        ↓
    [Retry]
```

## 3. Usage

### In WebSocket Route

This is automatically applied in `src/api/routes/websocket.py`:

```python
from src.services.websocket_service.error_classifier import (
    ErrorClassifier,
    ErrorSeverity
)

error_count = 0
max_error_tolerance = settings.websocket.max_error_tolerance
error_sleep_seconds = settings.websocket.error_backoff_seconds

while True:
    try:
        raw_message = await websocket.receive_text()
        error_count = 0  # Reset on success
        await websocket_manager.handle_message(connection_id, raw_message)

    except Exception as e:
        # Classify error
        severity = ErrorClassifier.classify(e)
        logger.error(f"Error handling message ({severity}): {e}")

        error_count += 1

        # Check if should retry
        if not ErrorClassifier.should_retry(e, error_count, max_error_tolerance):
            if severity == ErrorSeverity.FATAL:
                logger.error(f"Fatal error, closing connection")
            else:
                logger.error(f"Exceeded error tolerance ({error_count}/{max_error_tolerance})")
            break

        # Apply backoff
        backoff_delay = ErrorClassifier.get_backoff_delay(e, error_sleep_seconds)
        if backoff_delay > 0:
            logger.debug(f"Applying backoff: {backoff_delay}s")
            await asyncio.sleep(backoff_delay)

        continue  # Retry
```

### Custom Error Handling

```python
from src.services.websocket_service.error_classifier import ErrorClassifier

async def safe_operation(connection_id):
    errors = 0
    max_errors = 3

    while errors < max_errors:
        try:
            result = await risky_operation()
            return result

        except Exception as e:
            severity = ErrorClassifier.classify(e)

            if severity == ErrorSeverity.FATAL:
                logger.error(f"Fatal error: {e}")
                raise  # Don't retry fatal errors

            errors += 1
            if errors >= max_errors:
                logger.error(f"Max retries exceeded")
                raise

            delay = ErrorClassifier.get_backoff_delay(e, 0.5)
            if delay > 0:
                await asyncio.sleep(delay)
```

### Extending Error Classification

To add custom error types:

```python
from src.services.websocket_service.error_classifier import ErrorClassifier, ErrorSeverity

# Add custom exception mapping
ErrorClassifier.SEVERITY_MAP[MyCustomException] = ErrorSeverity.RECOVERABLE

# Or use inheritance check
class MyNetworkError(ConnectionError):
    pass

# Automatically classified as TRANSIENT (inherits from ConnectionError)
```

---

## Appendix

### A. Error Codes Reference

| Code | Severity | Meaning | Client Action |
|------|----------|---------|---------------|
| 1000 | Normal | Normal closure | None |
| 1011 | Fatal | Internal error | Log and notify user |
| 4000 | Fatal | Ping timeout | Reconnect immediately |
| 4001 | Fatal | Auth failed | Don't reconnect, fix token |
| 4002 | Recoverable | Concurrent turn | Wait for stream_end |
| 4003 | Info | Interrupted | Expected (user action) |
| 4004 | Recoverable | Turn not found | Ignore or refresh state |

### B. Error Tolerance Configuration

Located in `yaml_files/main.yml`:

```yaml
websocket:
  max_error_tolerance: 5        # Max consecutive errors
  error_backoff_seconds: 0.5    # Delay for recoverable errors
```

**Tuning Guidelines:**

For **production environments**:

```yaml
max_error_tolerance: 3          # Fail fast
error_backoff_seconds: 1.0      # Longer backoff
```

For **development/testing**:

```yaml
max_error_tolerance: 10         # More forgiving
error_backoff_seconds: 0.1      # Quick retry
```

For **high-reliability services**:

```yaml
max_error_tolerance: 5
error_backoff_seconds: 2.0      # Conservative
```

### C. Error Logging Best Practices

**Log Levels by Severity:**

```python
# TRANSIENT - DEBUG level (expected, temporary)
logger.debug(f"Transient error (will retry): {e}")

# RECOVERABLE - WARNING level (unusual but handleable)
logger.warning(f"Recoverable error (attempt {error_count}): {e}")

# FATAL - ERROR level (requires attention)
logger.error(f"Fatal error (closing connection): {e}", exc_info=True)
```

**Context Information:**

Always include:

- Connection ID
- Error count / max tolerance
- Severity classification
- Stack trace for fatal errors

### D. Common Error Patterns

**Pattern 1: Burst Errors**

```
TimeoutError → TimeoutError → TimeoutError → ConnectionResetError
```

- All TRANSIENT
- Likely network instability
- Retries exhaust quickly
- Solution: Increase max_error_tolerance or add exponential backoff

**Pattern 2: Malformed Messages**

```
ValidationError → ValidationError → ValidationError
```

- RECOVERABLE but repeating
- Client sending bad data
- Solution: Return clear error to client, log for debugging

**Pattern 3: Resource Exhaustion**

```
Normal → Normal → RuntimeError: "Cannot allocate memory"
```

- Sudden FATAL
- System resource issue
- Solution: Monitor system resources, add rate limiting

### E. Testing Error Handling

**Unit Test Example:**

```python
import pytest
from src.services.websocket_service.error_classifier import (
    ErrorClassifier, ErrorSeverity
)

def test_classify_transient_errors():
    assert ErrorClassifier.classify(TimeoutError()) == ErrorSeverity.TRANSIENT
    assert ErrorClassifier.classify(ConnectionResetError()) == ErrorSeverity.TRANSIENT

def test_classify_recoverable_errors():
    assert ErrorClassifier.classify(ValueError()) == ErrorSeverity.RECOVERABLE
    assert ErrorClassifier.classify(KeyError()) == ErrorSeverity.RECOVERABLE

def test_classify_fatal_errors():
    assert ErrorClassifier.classify(RuntimeError()) == ErrorSeverity.FATAL

def test_should_retry_logic():
    exc = TimeoutError()

    # Within tolerance
    assert ErrorClassifier.should_retry(exc, 1, 5) is True
    assert ErrorClassifier.should_retry(exc, 4, 5) is True

    # Exceeded tolerance
    assert ErrorClassifier.should_retry(exc, 5, 5) is False

    # Fatal never retry
    fatal_exc = RuntimeError()
    assert ErrorClassifier.should_retry(fatal_exc, 1, 5) is False

def test_backoff_delays():
    transient = TimeoutError()
    recoverable = ValueError()
    fatal = RuntimeError()

    assert ErrorClassifier.get_backoff_delay(transient, 0.5) == 0.0
    assert ErrorClassifier.get_backoff_delay(recoverable, 0.5) == 0.5
    assert ErrorClassifier.get_backoff_delay(fatal, 0.5) == 0.0
```

### F. Related Documents

- [Connection Lifecycle](./WebSocket_ConnectionLifecycle.md) - Connection management
- [WebSocket API Guide](./WEBSOCKET_API_GUIDE.md) - Main API reference
- [Error Message](./WebSocket_ErrorMessage.md) - Error message format
