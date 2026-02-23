"""Test cases for tool event logging (backend only, not sent to clients)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

import pytest
from loguru import logger

from src.services.websocket_service.message_processor import (
    MessageProcessor,
)


class MockLogHandler:
    """Mock handler to capture log records with extra fields."""

    def __init__(self):
        self.records = []

    def sink(self, message):
        """Capture log messages.

        Args:
            message: loguru Message object containing record attribute
        """
        # message.record contains all the log record data including extra fields
        self.records.append(dict(message.record))

    def get_tool_logs(self):
        """Get only tool-related log records."""
        tool_logs = []
        for record in self.records:
            message = record.get("message", "")
            extra = record.get("extra", {})

            # Extra fields might be double-nested under "extra"
            if "extra" in extra:
                extra = extra["extra"]

            # Check if this is a tool-related log
            if (
                "Tool call" in message
                or "Tool result" in message
                or "tool_name" in extra
            ):
                # Flatten the record for easier testing
                level_obj = record.get("level")
                flat_record = {
                    "message": message,
                    "level": (
                        level_obj.name if hasattr(level_obj, "name") else str(level_obj)
                    ),
                    "timestamp": record.get("time"),
                }
                # Add extra fields
                flat_record.update(extra)
                tool_logs.append(flat_record)

        return tool_logs

    def clear(self):
        """Clear captured records."""
        self.records.clear()


@pytest.fixture
def log_handler():
    """Create a mock log handler and add it to loguru."""
    handler = MockLogHandler()
    handler_id = logger.add(handler.sink, format="{message}", serialize=True)
    yield handler
    logger.remove(handler_id)
    handler.clear()


@pytest.fixture
def processor() -> MessageProcessor:
    """Create a MessageProcessor instance for each test."""
    return MessageProcessor(
        connection_id=uuid4(),
        user_id="test_user",
    )


async def mock_agent_stream_with_tools() -> AsyncIterator[Dict[str, Any]]:
    """Mock agent stream that includes tool events."""
    # Stream start
    yield {"type": "stream_start"}

    # Some initial tokens
    yield {"type": "stream_token", "data": "Let me search for that information. "}

    # Tool call event
    yield {
        "type": "tool_call",
        "tool_name": "search_documents",
        "args": '{"query": "test query", "index": "test_index"}',
    }

    # Simulate tool execution time
    await asyncio.sleep(0.1)

    # Tool result event
    yield {
        "type": "tool_result",
        "result": "Found 5 relevant documents",
        "node": "tools",
    }

    # More tokens after tool execution
    yield {"type": "stream_token", "data": "Based on the search results, "}
    yield {"type": "stream_token", "data": "I found relevant information."}

    # Stream end
    yield {"type": "stream_end"}


async def mock_agent_stream_with_error() -> AsyncIterator[Dict[str, Any]]:
    """Mock agent stream with a tool that fails."""
    yield {"type": "stream_start"}
    yield {"type": "stream_token", "data": "Attempting to execute tool... "}

    # Tool call
    yield {
        "type": "tool_call",
        "tool_name": "failing_tool",
        "args": '{"param": "value"}',
    }

    await asyncio.sleep(0.05)

    # Tool result with error
    yield {
        "type": "tool_result",
        "result": "Error: Tool execution failed due to timeout",
        "node": "tools",
    }

    yield {"type": "stream_end"}


@pytest.mark.asyncio
async def test_tool_events_not_sent_to_client(processor: MessageProcessor):
    """Test that tool events are not forwarded to the client event stream."""
    session_id = "test_conv_123"
    turn_id = await processor.start_turn(
        session_id=session_id,
        user_input="Test message",
        agent_stream=mock_agent_stream_with_tools(),
    )

    # Collect all events sent to client
    client_events = []
    async for event in processor.stream_events(turn_id):
        client_events.append(event)

    # Verify no tool_call or tool_result events are sent to client
    event_types = [event.get("type") for event in client_events]

    assert "tool_call" not in event_types, "tool_call should not be sent to client"
    assert "tool_result" not in event_types, "tool_result should not be sent to client"

    # Verify we still get other events
    assert "stream_start" in event_types
    assert "stream_end" in event_types

    await processor.shutdown()


@pytest.mark.asyncio
async def test_tool_events_are_logged_with_metadata(
    processor: MessageProcessor, log_handler: MockLogHandler
):
    """Test that tool events are logged with structured metadata."""
    session_id = "test_conv_456"
    turn_id = await processor.start_turn(
        session_id=session_id,
        user_input="Test message",
        agent_stream=mock_agent_stream_with_tools(),
    )

    # Consume all events
    async for _ in processor.stream_events(turn_id):
        pass

    # Give a moment for async logging
    await asyncio.sleep(0.1)

    # Check logged tool events
    tool_logs = log_handler.get_tool_logs()

    # Should have at least 2 logs: tool_call start and tool_result
    assert len(tool_logs) >= 2, f"Expected at least 2 tool logs, got {len(tool_logs)}"

    # Find tool_call log
    tool_call_logs = [
        log for log in tool_logs if "started" in log.get("message", "").lower()
    ]
    assert len(tool_call_logs) >= 1, "Should have tool call started log"

    # Verify tool_call log has required fields
    tool_call_log = tool_call_logs[0]
    assert tool_call_log.get("session_id") == session_id
    assert tool_call_log.get("turn_id") == turn_id
    assert tool_call_log.get("tool_name") == "search_documents"
    assert "query" in tool_call_log.get("args", "")
    assert tool_call_log.get("status") == "started"

    # Find tool_result log
    tool_result_logs = [
        log for log in tool_logs if "result" in log.get("message", "").lower()
    ]
    assert len(tool_result_logs) >= 1, "Should have tool result log"

    # Verify tool_result log has required fields
    tool_result_log = tool_result_logs[0]
    assert tool_result_log.get("session_id") == session_id
    assert tool_result_log.get("turn_id") == turn_id
    assert tool_result_log.get("tool_name") is not None
    assert tool_result_log.get("status") in ["success", "error"]

    await processor.shutdown()


@pytest.mark.asyncio
async def test_tool_duration_is_captured(
    processor: MessageProcessor, log_handler: MockLogHandler
):
    """Test that tool execution duration is logged in milliseconds."""
    session_id = "test_conv_789"
    turn_id = await processor.start_turn(
        session_id=session_id,
        user_input="Test message",
        agent_stream=mock_agent_stream_with_tools(),
    )

    start_time = time.time()

    # Consume all events
    async for _ in processor.stream_events(turn_id):
        pass

    await asyncio.sleep(0.1)

    # Check tool result logs for duration
    tool_logs = log_handler.get_tool_logs()
    tool_result_logs = [
        log for log in tool_logs if "result" in log.get("message", "").lower()
    ]

    assert len(tool_result_logs) >= 1, "Should have tool result log"

    tool_result_log = tool_result_logs[0]
    duration_ms = tool_result_log.get("duration_ms")

    # Duration should be present and reasonable (between 0 and total test time)
    assert duration_ms is not None, "duration_ms should be logged"
    assert isinstance(duration_ms, int), "duration_ms should be an integer"
    assert duration_ms >= 0, "duration_ms should be non-negative"
    # Should be less than total elapsed time (with some margin)
    elapsed_ms = (time.time() - start_time) * 1000
    assert duration_ms < elapsed_ms + 1000, "duration_ms should be reasonable"

    await processor.shutdown()


@pytest.mark.asyncio
async def test_tool_error_status_detected(
    processor: MessageProcessor, log_handler: MockLogHandler
):
    """Test that tool errors are detected and logged with error status."""
    session_id = "test_conv_error"
    turn_id = await processor.start_turn(
        session_id=session_id,
        user_input="Test message",
        agent_stream=mock_agent_stream_with_error(),
    )

    # Consume all events
    async for _ in processor.stream_events(turn_id):
        pass

    await asyncio.sleep(0.1)

    # Check tool result logs
    tool_logs = log_handler.get_tool_logs()
    tool_result_logs = [
        log for log in tool_logs if "result" in log.get("message", "").lower()
    ]

    assert len(tool_result_logs) >= 1, "Should have tool result log"

    tool_result_log = tool_result_logs[0]
    status = tool_result_log.get("status")

    # Status should be "error" because the result contains "Error:"
    assert status == "error", f"Expected error status, got {status}"

    await processor.shutdown()


@pytest.mark.asyncio
async def test_multiple_tools_in_sequence(
    processor: MessageProcessor, log_handler: MockLogHandler
):
    """Test logging when multiple tools are called in sequence."""

    async def multi_tool_stream() -> AsyncIterator[Dict[str, Any]]:
        yield {"type": "stream_start"}
        yield {"type": "stream_token", "data": "First tool... "}

        # First tool
        yield {
            "type": "tool_call",
            "tool_name": "tool_one",
            "args": '{"arg": "1"}',
        }
        await asyncio.sleep(0.05)
        yield {"type": "tool_result", "result": "Result 1", "node": "tools"}

        yield {"type": "stream_token", "data": "Second tool... "}

        # Second tool
        yield {
            "type": "tool_call",
            "tool_name": "tool_two",
            "args": '{"arg": "2"}',
        }
        await asyncio.sleep(0.05)
        yield {"type": "tool_result", "result": "Result 2", "node": "tools"}

        yield {"type": "stream_end"}

    session_id = "test_conv_multi"
    turn_id = await processor.start_turn(
        session_id=session_id,
        user_input="Test message",
        agent_stream=multi_tool_stream(),
    )

    # Consume all events
    async for _ in processor.stream_events(turn_id):
        pass

    await asyncio.sleep(0.1)

    # Check that both tools are logged
    tool_logs = log_handler.get_tool_logs()

    # Should have logs for both tool calls and both results
    tool_call_logs = [
        log for log in tool_logs if "started" in log.get("message", "").lower()
    ]
    assert len(tool_call_logs) >= 2, "Should have 2 tool call logs"

    # Verify different tool names
    tool_names = [log.get("tool_name") for log in tool_call_logs]
    assert "tool_one" in tool_names
    assert "tool_two" in tool_names

    await processor.shutdown()


@pytest.mark.asyncio
async def test_json_log_format(log_handler: MockLogHandler):
    """Test that logs contain structured extra fields."""
    # Trigger a log with extra fields
    logger.info(
        "Test tool log",
        extra={
            "session_id": "test_123",
            "turn_id": "turn_456",
            "tool_name": "test_tool",
            "args": '{"test": "value"}',
            "status": "success",
            "duration_ms": 100,
        },
    )

    await asyncio.sleep(0.1)

    # Verify the log was captured
    assert len(log_handler.records) > 0, "Should have captured at least one log"

    # Get the last record
    record = log_handler.records[-1]

    # Verify it's a dict (loguru record)
    assert isinstance(record, dict), "Log should be a dictionary"

    # Verify message
    assert record.get("message") == "Test tool log"

    # Verify extra fields are present in the record
    extra = record.get("extra", {})
    # Extra fields might be double-nested
    if "extra" in extra:
        extra = extra["extra"]

    assert extra.get("session_id") == "test_123"
    assert extra.get("turn_id") == "turn_456"
    assert extra.get("tool_name") == "test_tool"
    assert extra.get("status") == "success"
    assert extra.get("duration_ms") == 100
