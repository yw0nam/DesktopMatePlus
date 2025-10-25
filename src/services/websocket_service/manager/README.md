# WebSocket Manager Module

This module provides WebSocket connection management, message routing, authentication, and heartbeat monitoring for the DesktopMatePlus application.

## Module Structure

The WebSocket Manager has been modularized into several focused components:

### Core Files

- **`__init__.py`** - Public API exports for the module
- **`connection.py`** - ConnectionState data model
- **`handlers.py`** - Message handling logic (authorize, chat, pong, interrupt)
- **`heartbeat.py`** - Heartbeat monitoring with ping/pong
- **`websocket_manager.py`** - Main orchestrator class and global instance

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WebSocketManager                          │
│  (Orchestrates connections, routing, and lifecycle)         │
└───────────────┬──────────────────┬──────────────────────────┘
                │                  │
        ┌───────▼──────────┐  ┌───▼─────────────┐
        │  MessageHandler  │  │ HeartbeatMonitor│
        │  - Authorization │  │  - Ping/pong    │
        │  - Chat routing  │  │  - Timeout      │
        │  - Interrupts    │  │  - Disconnect   │
        └──────────────────┘  └─────────────────┘
```

## Components

### WebSocketManager (websocket_manager.py)

The main orchestrator that:
- Manages connection lifecycle (connect, disconnect, send messages)
- Routes incoming messages to appropriate handlers
- Delegates to MessageHandler and HeartbeatMonitor
- Maintains global connection registry
- Provides connection statistics

**Key Methods:**
- `connect()` - Accept new WebSocket connection
- `disconnect()` - Cleanup connection resources
- `send_message()` - Send message to specific connection
- `broadcast_message()` - Send message to all authenticated connections
- `handle_message()` - Route incoming messages by type

### MessageHandler (handlers.py)

Handles all message types:
- **Authorization**: Validates tokens, initializes MessageProcessor
- **Chat Messages**: Routes to agent service, manages conversation turns
- **Pong Responses**: Updates heartbeat timestamps
- **Interrupts**: Cancels active conversation turns

**Key Methods:**
- `handle_authorize()` - Process authorization requests
- `handle_chat_message()` - Route chat to agent service
- `handle_pong()` - Update pong timestamp
- `handle_interrupt()` - Cancel active turns

**Helper Functions:**
- `forward_turn_events()` - Stream MessageProcessor events to client

### HeartbeatMonitor (heartbeat.py)

Monitors connection health:
- **Ping Loop**: Sends periodic ping messages
- **Timeout Detection**: Closes connections that don't respond
- **Background Tasks**: Runs per-connection heartbeat loops

**Key Methods:**
- `heartbeat_loop()` - Main monitoring loop for a connection

### ConnectionState (connection.py)

Data model for connection state:
- WebSocket reference
- Authentication status and user ID
- Heartbeat timestamps (last ping, last pong)
- MessageProcessor instance
- Creation timestamp

## Usage

```python
from src.services.websocket_service import websocket_manager

# In WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await websocket_manager.connect(websocket)

    try:
        while True:
            raw_message = await websocket.receive_text()
            await websocket_manager.handle_message(connection_id, raw_message)
    except WebSocketDisconnect:
        websocket_manager.disconnect(connection_id)
```

## Message Flow

```
Client WebSocket
    │
    ├─► AUTHORIZE ─────────► MessageHandler.handle_authorize()
    │                              │
    │                              ├─► validate_token()
    │                              ├─► Create MessageProcessor
    │                              └─► Send AUTHORIZE_SUCCESS
    │
    ├─► CHAT_MESSAGE ──────► MessageHandler.handle_chat_message()
    │                              │
    │                              ├─► Get AgentService
    │                              ├─► Start conversation turn
    │                              └─► Forward events to client
    │
    ├─► PONG ──────────────► MessageHandler.handle_pong()
    │                              └─► Update timestamp
    │
    └─► INTERRUPT_STREAM ──► MessageHandler.handle_interrupt()
                                   └─► Cancel active turns

HeartbeatMonitor
    │
    ├─► Send PING every 30s
    └─► Check for PONG within 10s timeout
```

## Design Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Dependency Injection**: Handlers receive callbacks, not direct references
3. **Async-First**: All operations are async-aware and non-blocking
4. **Resource Cleanup**: Deterministic cleanup on disconnect
5. **Error Handling**: Graceful error handling with proper logging

## Configuration

```python
# Custom ping/pong intervals
manager = WebSocketManager(
    ping_interval=30,  # seconds between pings
    pong_timeout=10,   # seconds to wait for pong
)
```

## Testing

Tests are organized to verify each component:
- `test_websocket_service.py` - Manager, handlers, and message routing
- `test_websocket_gateway.py` - End-to-end WebSocket integration

Run tests:
```bash
uv run pytest tests/test_websocket*.py -v
```

## Integration Points

### With MessageProcessor
- Creates MessageProcessor on successful authorization
- Forwards agent events to WebSocket client
- Manages conversation turn lifecycle

### With AgentService
- Retrieves agent service via `get_agent_service()`
- Streams agent responses through MessageProcessor
- Handles agent errors gracefully

### With Models
- Uses Pydantic models from `src.models.websocket`
- Validates incoming messages
- Serializes outgoing messages to JSON
