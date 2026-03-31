# Release Notes - WebSocket Connection Management Improvements

Updated: 2026-03-03

## [feat/improved_websocket](https://github.com/your-repo/backend/compare/main...feat/improved_websocket) (2026-03-03)

> Comprehensive improvements to WebSocket connection lifecycle management, error handling, and configuration.

### Upgrade Steps

* **[ACTION REQUIRED]** Update `yaml_files/main.yml` with new WebSocket configuration structure:

  ```yaml
  # OLD
  websocket:
    max_error_tolerance: 5
    error_backoff_seconds: 0.5
    inactivity_timeout_seconds: 300

  # NEW
  websocket:
    ping_interval_seconds: 30
    pong_timeout_seconds: 10
    max_error_tolerance: 5
    error_backoff_seconds: 0.5
    inactivity_timeout_seconds: 300
    disconnect_timeout_seconds: 5.0
  ```

* **[ACTION REQUIRED]** Update all `disconnect()` calls to use `await`:

  ```python
  # OLD
  websocket_manager.disconnect(connection_id)

  # NEW
  await websocket_manager.disconnect(connection_id)
  ```

* **[OPTIONAL]** Review and adjust timeout values based on your network conditions
* **[RECOMMENDED]** Update client code to handle new error code 4002 (concurrent turn rejection)

### Breaking Changes

* `WebSocketManager.disconnect()` is now async - all callers must `await` it
* `WebSocketManager.__init__()` no longer accepts `ping_interval` and `pong_timeout` as parameters (now loaded from settings)
* `HeartbeatMonitor` and `MessageHandler` now accept `close_connection_fn` instead of `disconnect_fn`

### New Features

* **Error Classification System** - Automatic error categorization and intelligent retry logic
  * `ErrorClassifier` with three severity levels: TRANSIENT, RECOVERABLE, FATAL
  * Automatic backoff strategy based on error type
  * See [WebSocket_ErrorHandling.md](../websocket/WebSocket_ErrorHandling.md)

* **Graceful Disconnect** - Standardized connection cleanup with proper resource management
  * `_close_connection()` method ensures consistent cleanup order
  * MessageProcessor graceful shutdown with configurable timeout
  * Connection state transition tracking with `is_closing` flag

* **Concurrent Turn Protection** - Prevents multiple simultaneous chat messages per connection
  * Clear error messages with current turn status
  * Error code 4002 for client-side handling
  * Improved UX for message queuing

* **Comprehensive Documentation** - New detailed guides
  * [WebSocket_ConnectionLifecycle.md](../websocket/WebSocket_ConnectionLifecycle.md)
  * [WebSocket_ErrorHandling.md](../websocket/WebSocket_ErrorHandling.md)
  * Updated [WEBSOCKET_API_GUIDE.md](../websocket/WEBSOCKET_API_GUIDE.md)

### Bug Fixes

* Fixed heartbeat timeout logic - first ping no longer causes false timeout
* Fixed time calculation for pong timeout - now correctly uses `time_since_last_pong > (ping_interval + pong_timeout)`
* Fixed resource cleanup order - MessageProcessor now shuts down before connection removal
* Fixed race condition in disconnect - `is_closing` flag prevents operations during shutdown

### Performance Improvements

* **Faster Error Recovery** - TRANSIENT errors retry immediately without backoff
* **Configurable Timeouts** - All timeouts now loaded from YAML for easy tuning
* **Test Compatibility** - WebSocketManager can initialize without full settings (fallback to defaults)
* **Async Cleanup** - Non-blocking disconnect with proper timeout handling

### Other Changes

* Added `is_closing` flag to `ConnectionState` for clean shutdown signaling
* Updated `WebSocketConfig` with new timeout fields
* Improved error messages with detailed context (turn_id, status)
* Enhanced logging with severity-appropriate levels
* Reformatted code with ruff linting
* Updated test suite (215 tests passing)

---

## Implementation Details

### Configuration Changes

New fields in `yaml_files/main.yml`:

```yaml
websocket:
  ping_interval_seconds: 30       # Heartbeat interval
  pong_timeout_seconds: 10        # Pong response timeout
  disconnect_timeout_seconds: 5.0  # Graceful disconnect timeout (NEW)
```

### Error Code Reference

| Code | Trigger | Description |
|------|---------|-------------|
| 1000 | Normal closure | Clean disconnect |
| 1011 | Internal error | Server-side failure |
| 4000 | Ping timeout | No pong response |
| 4001 | Auth failed | Invalid token |
| 4002 | Concurrent turn | Multiple simultaneous messages (NEW) |
| 4003 | Interrupted | User requested interruption |
| 4004 | Not found | Turn not found |

### Architecture Changes

```text
Before:
disconnect() → immediate cleanup → race conditions

After:
disconnect() → set is_closing → shutdown processor → close websocket → cleanup
               ↑
               Graceful with timeout protection
```

### Migration Examples

**Example 1: Updating Disconnect Calls**

```python
# Before
def cleanup():
    websocket_manager.disconnect(connection_id)

# After
async def cleanup():
    await websocket_manager.disconnect(connection_id)
```

**Example 2: Handling Concurrent Turn Errors**

```javascript
// Client-side handling
socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === 'error' && msg.code === 4002) {
        console.warn('Server is busy processing your previous message');
        // Queue message or show "Please wait..." UI
    }
};
```

**Example 3: Custom Error Handling**

```python
from src.services.websocket_service.error_classifier import ErrorClassifier

try:
    await operation()
except Exception as e:
    severity = ErrorClassifier.classify(e)
    if severity == ErrorSeverity.FATAL:
        await emergency_shutdown()
    else:
        await retry_with_backoff()
```

---

## Testing

All tests passing (215 passed, 7 skipped):
* WebSocket tests: 39/39 ✅
* MessageProcessor tests: 13/13 ✅
* Integration tests: All passing ✅

Run tests:

```bash
uv run pytest tests/websocket/ -v
uv run pytest tests/core/test_message_processor.py -v
```

## Related Documents

* [WebSocket API Guide](../websocket/WEBSOCKET_API_GUIDE.md)
* [Connection Lifecycle](../websocket/WebSocket_ConnectionLifecycle.md)
* [Error Handling](../websocket/WebSocket_ErrorHandling.md)
* [Development Guidelines](../guidelines/DOCUMENT_GUIDE.md)
