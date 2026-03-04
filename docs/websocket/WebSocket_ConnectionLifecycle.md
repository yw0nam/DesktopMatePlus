# WebSocket Connection Lifecycle

Updated: 2026-03-03

## 1. Synopsis

- **Purpose**: Manage WebSocket connection from creation to graceful termination
- **I/O**: Connection events → State transitions → Resource cleanup

## 2. Core Logic

### Connection States

```text
[Connecting] → [Connected] → [Authenticated] → [Active] → [Closing] → [Closed]
     ↓              ↓              ↓              ↓           ↓
  Accept       Heartbeat       Chat/Stream    Disconnect   Cleanup
```

### Connection Establishment

1. **Accept Connection**

   ```python
   connection_id = await websocket_manager.connect(websocket)
   # Returns: UUID for this connection
   # Creates: ConnectionState with is_closing=False
   # Starts: Heartbeat task automatically
   ```

2. **Authentication Required**
   - First message MUST be `authorize`
   - Other messages rejected with error
   - Failed auth → connection closed with code 4001

3. **Heartbeat Activation**
   - Ping sent every 30s (configurable)
   - First ping skipped from timeout check
   - Pong expected within (interval + timeout)

### Connection Termination

#### Graceful Disconnect Flow

```python
await websocket_manager.disconnect(connection_id)
```

**Steps (Standardized):**

1. Set `is_closing = True` (prevents new messages)
2. Shutdown MessageProcessor gracefully (waits for active turns)
3. Close WebSocket with appropriate code/reason
4. Remove from connections dict
5. Cancel heartbeat task automatically

**Timeout Protection:**

- MessageProcessor shutdown: 5s timeout (configurable)
- If timeout exceeded, forces shutdown
- Connection always cleaned up

#### Termination Triggers

| Trigger | Code | Description | Notify Client |
|---------|------|-------------|---------------|
| **Ping Timeout** | 4000 | No pong for (interval + timeout)s | Yes |
| **Auth Failed** | 4001 | Invalid token on authorize | Yes |
| **Send Failed** | 1011 | Error sending message to client | No |
| **Inactivity** | 1000 | No messages for 300s+  | No (client timeout) |
| **Max Errors** | Varies | Too many errors (5+ consecutive) | Depends on error |
| **Client Disconnect** | 1000 | Client closed connection | No (already gone) |

### State Management

**ConnectionState Fields:**

```python
connection_id: UUID           # Unique identifier
websocket: WebSocket          # FastAPI WebSocket object
is_authenticated: bool        # Auth status
is_closing: bool             # Termination in progress
last_ping_time: float        # Last ping timestamp
last_pong_time: float        # Last pong timestamp
user_id: Optional[str]       # User identifier
message_processor: Optional  # Turn manager
```

**Key Rules:**

- `is_closing` checked by heartbeat to stop pings
- MessageProcessor only created after authentication
- Connection can exist without MessageProcessor
- All async cleanup uses configurable timeouts

## 3. Usage

### Client Connection Pattern

```javascript
let socket;
let reconnectAttempts = 0;
const MAX_RECONNECT = 5;

function connect() {
    socket = new WebSocket('ws://127.0.0.1:5500/v1/chat/stream');

    socket.onopen = () => {
        console.log('Connected');
        reconnectAttempts = 0;

        // Immediate auth required
        socket.send(JSON.stringify({
            type: 'authorize',
            token: getAuthToken()
        }));
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'ping') {
            // MUST respond to maintain connection
            socket.send(JSON.stringify({ type: 'pong' }));
        } else if (msg.type === 'authorize_success') {
            console.log('Authenticated:', msg.connection_id);
            // Now safe to send chat messages
        } else if (msg.type === 'error' && msg.code === 4002) {
            // Concurrent turn rejected - wait for stream_end
            console.warn('Please wait for current message to complete');
        }
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    socket.onclose = (event) => {
        console.log('Closed:', event.code, event.reason);

        // Reconnect logic based on close code
        if (event.code === 4001) {
            // Auth failed - don't reconnect
            console.error('Authentication failed');
        } else if (event.code === 4000) {
            // Ping timeout - immediate reconnect
            console.warn('Ping timeout - reconnecting');
            reconnect();
        } else if (reconnectAttempts < MAX_RECONNECT) {
            // Other errors - exponential backoff
            setTimeout(reconnect, Math.pow(2, reconnectAttempts) * 1000);
        }
    };
}

function reconnect() {
    reconnectAttempts++;
    console.log(`Reconnect attempt ${reconnectAttempts}/${MAX_RECONNECT}`);
    connect();
}

// Initial connection
connect();
```

### Server Disconnect Pattern

```python
# From any async context
await websocket_manager.disconnect(connection_id)

# Or with custom close parameters
await websocket_manager._close_connection(
    connection_id=connection_id,
    code=4000,
    reason="Custom reason",
    notify_client=True
)
```

---

## Appendix

### A. Configuration Reference

Located in `yaml_files/main.yml`:

```yaml
settings:
  websocket:
    ping_interval_seconds: 30       # Default: 30
    pong_timeout_seconds: 10        # Default: 10
    max_error_tolerance: 5          # Default: 5
    error_backoff_seconds: 0.5      # Default: 0.5
    inactivity_timeout_seconds: 300 # Default: 300 (5 min)
    disconnect_timeout_seconds: 5.0 # Default: 5.0
```

**Tuning Guidelines:**

- **Lower latency network**: Reduce ping_interval to 15s
- **High latency/mobile**: Increase pong_timeout to 20s
- **Long-running operations**: Increase disconnect_timeout to 10s
- **Public API**: Reduce inactivity_timeout to 120s

### B. Heartbeat Algorithm

```python
first_ping = True
while connection_active:
    await send_ping()
    await sleep(ping_interval)

    if first_ping:
        first_ping = False
        continue  # Skip first timeout check

    if last_pong_time is None:
        continue  # No pong received yet

    time_since_pong = now() - last_pong_time
    max_allowed = ping_interval + pong_timeout

    if time_since_pong > max_allowed:
        await close_connection(code=4000, reason="Ping timeout")
        break
```

### C. Concurrent Turn Protection

**Problem:** User sends chat message while previous message is still processing

**Solution:**

1. MessageProcessor prevents concurrent turns with lock
2. Raises RuntimeError with detailed message
3. Handler catches and returns error code 4002
4. Client receives error and can:
   - Wait for stream_end
   - Call interrupt_stream first
   - Queue message on client side

**Error Response:**

```json
{
  "type": "error",
  "error": "Another turn is already active (turn_id: abc-123, status: PROCESSING). Please wait for the current turn to complete or interrupt it before starting a new turn.",
  "code": 4002
}
```

### D. Related Documents

- [WebSocket API Guide](./WEBSOCKET_API_GUIDE.md) - Main API reference
- [Error Handling](./WebSocket_ErrorHandling.md) - Error classification system
- [WebSocket Service](../feature/service/WebSocket_Service.md) - Implementation details

### E. Troubleshooting

**Connection closes immediately after opening:**

- Check if auth message is sent first
- Verify token is valid
- Check server logs for auth errors

**Frequent ping timeouts:**

- Increase pong_timeout_seconds
- Check client pong implementation
- Verify network stability

**MessageProcessor shutdown timeouts:**

- Increase disconnect_timeout_seconds
- Check for blocking operations in turn processing
- Review agent service streaming behavior

**Connection not cleaning up:**

- Verify disconnect() is awaited
- Check for exception catching that prevents cleanup
- Review heartbeat task cancellation
