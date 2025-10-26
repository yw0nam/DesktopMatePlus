# WebSocket API - Tool Event Logging

## Overview

Tool events (`tool_call` and `tool_result`) are **not forwarded to WebSocket clients**. They are logged server-side only for observability and debugging purposes.

## Design Decision

While the agent service generates `tool_call` and `tool_result` events during tool execution, these events are intentionally excluded from the client-facing WebSocket stream. This design choice:

1. **Simplifies Client Implementation**: Clients don't need to handle intermediate tool execution states
2. **Reduces Network Traffic**: Eliminates unnecessary event transmission
3. **Maintains Security**: Prevents exposure of internal tool implementation details
4. **Improves User Experience**: Clients receive only actionable `tts_ready_chunk` events

## Server-Side Logging

Tool events are logged with structured metadata for operational monitoring:

### Tool Call Log Fields
- `conversation_id`: Logical conversation identifier
- `turn_id`: Unique turn identifier
- `tool_name`: Name of the tool being called
- `args`: JSON string of tool arguments
- `status`: Always "started" for tool calls
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (typically INFO)

### Tool Result Log Fields
- `conversation_id`: Logical conversation identifier
- `turn_id`: Unique turn identifier
- `tool_name`: Name of the tool that executed
- `duration_ms`: Execution duration in milliseconds
- `status`: Either "success" or "error"
- `node`: Execution node (typically "tools")
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (typically INFO)

## Example Log Output

### JSON Format (Production)
```json
{
  "timestamp": "2025-10-26T22:56:32.439448+09:00",
  "level": "INFO",
  "message": "Tool call started",
  "module": "event_handlers",
  "function": "_log_tool_call",
  "line": 285,
  "conversation_id": "test_conv_456",
  "turn_id": "8a6a993f-20b6-4cb2-bce1-caa982870e9d",
  "tool_name": "search_documents",
  "args": "{\"query\": \"test query\", \"index\": \"test_index\"}",
  "status": "started"
}
```

```json
{
  "timestamp": "2025-10-26T22:56:32.539448+09:00",
  "level": "INFO",
  "message": "Tool result received",
  "module": "event_handlers",
  "function": "_log_tool_result",
  "line": 334,
  "conversation_id": "test_conv_456",
  "turn_id": "8a6a993f-20b6-4cb2-bce1-caa982870e9d",
  "tool_name": "search_documents",
  "duration_ms": 100,
  "status": "success",
  "node": "tools"
}
```

### Text Format (Development)
```
2025-10-26 22:56:32.439 | INFO | event_handlers:_log_tool_call:285 - Tool call started
2025-10-26 22:56:32.539 | INFO | event_handlers:_log_tool_result:334 - Tool result received
```

## Client-Facing Events

Clients receive only the following event types:

- `stream_start`: Conversation turn started
- `tts_ready_chunk`: Complete sentence ready for TTS and display
- `stream_end`: Conversation turn completed
- `error`: Error occurred during processing

Tool execution is transparent to the client - they see only the final generated text in `tts_ready_chunk` events.

## Configuration

### Enable JSON Logging

Set environment variables:
```bash
JSON_LOGGING=true    # Enable JSON-structured logs (default: true)
LOG_LEVEL=INFO       # Set log level (default: INFO)
```

### Disable JSON Logging (Development)

For human-readable logs during development:
```bash
JSON_LOGGING=false
LOG_LEVEL=DEBUG
```

## Implementation

Tool event logging is implemented in:
- `src/services/websocket_service/message_processor/event_handlers.py`
  - `_log_tool_call()`: Logs tool calls with start time tracking
  - `_log_tool_result()`: Logs tool results with duration calculation

- `src/core/logger.py`
  - `setup_json_logging()`: Configures JSON-structured logging using loguru's built-in `serialize=True`

## Testing

Comprehensive tests verify tool event logging behavior:
```bash
uv run pytest tests/test_tool_event_logging.py -v
```

Test coverage includes:
- Tool events are not sent to clients
- Tool events are logged with all required metadata
- Duration is accurately captured in milliseconds
- Error status is properly detected
- Multiple sequential tools are logged correctly
- JSON format includes structured extra fields

## Monitoring & Observability

Use log aggregation tools (e.g., ELK Stack, Splunk, Datadog) to:

1. **Track Tool Usage**: Query by `tool_name` to see which tools are used most
2. **Monitor Performance**: Analyze `duration_ms` for slow tool executions
3. **Debug Failures**: Filter by `status: "error"` to find failing tools
4. **Trace Conversations**: Follow `conversation_id` across multiple turns
5. **Correlate Events**: Use `turn_id` to link tool calls with their results

## Future Enhancements

Potential improvements for production deployments:

1. **Prometheus Metrics**: Export tool execution metrics (count, duration, errors)
2. **Distributed Tracing**: Add OpenTelemetry spans for tool executions
3. **Persistent Storage**: Store tool logs in Redis/PostgreSQL for retention
4. **Alert Rules**: Configure alerts for tool failures or slow executions
