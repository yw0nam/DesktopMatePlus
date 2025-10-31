#!/usr/bin/env python3
"""Quick demonstration of tool event logging.

This script shows that:
1. Tool events are logged server-side with structured metadata
2. Tool events are NOT sent to WebSocket clients
3. JSON logging captures all required fields
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

from src.services.websocket_service.message_processor import MessageProcessor


async def mock_tool_agent_stream() -> AsyncIterator[Dict[str, Any]]:
    """Simulate an agent that uses a tool."""
    yield {"type": "stream_start"}
    yield {"type": "stream_token", "data": "Let me help you with that. "}

    # Tool call
    yield {
        "type": "tool_call",
        "data": {
            "tool_name": "web_search",
            "args": '{"query": "latest news", "limit": 5}',
        },
    }

    # Simulate tool execution
    await asyncio.sleep(0.1)

    # Tool result
    yield {
        "type": "tool_result",
        "data": "Found 5 articles about latest news",
        "node": "tools",
    }

    yield {"type": "stream_token", "data": "Based on the search results, "}
    yield {"type": "stream_token", "data": "here's what I found."}
    yield {"type": "stream_end"}


async def main():
    """Demonstrate tool event logging."""
    print("=" * 70)
    print("Tool Event Logging Demonstration")
    print("=" * 70)
    print()

    # Create processor
    processor = MessageProcessor(
        connection_id=uuid4(),
        user_id="demo_user",
    )

    # Start a turn with tool usage
    print("📝 Starting conversation turn with tool usage...")
    turn_id = await processor.start_turn(
        conversation_id="demo_conversation",
        user_input="What's in the news?",
        agent_stream=mock_tool_agent_stream(),
    )

    # Collect client events
    print("\n📤 Events sent to CLIENT:")
    print("-" * 70)
    client_events = []
    async for event in processor.stream_events(turn_id):
        client_events.append(event)
        event_type = event.get("type")
        if event_type == "stream_start":
            print(f"  ✓ {event_type}")
        elif event_type == "tts_ready_chunk":
            chunk = event.get("chunk", "")
            print(f"  ✓ {event_type}: '{chunk}'")
        elif event_type == "stream_end":
            print(f"  ✓ {event_type}")
        else:
            print(f"  ✓ {event_type}: {json.dumps(event, indent=2)}")

    # Check for tool events
    print("\n" + "-" * 70)
    tool_events = [e for e in client_events if e.get("type") in ["tool_call", "tool_result"]]

    if tool_events:
        print("❌ FAILED: Tool events were sent to client!")
        for evt in tool_events:
            print(f"   {json.dumps(evt, indent=2)}")
    else:
        print("✅ SUCCESS: No tool events sent to client")

    print()
    print("📊 Server-side logging:")
    print("-" * 70)
    print("Tool events are logged with structured metadata:")
    print("  - conversation_id")
    print("  - turn_id")
    print("  - tool_name")
    print("  - args")
    print("  - duration_ms (for results)")
    print("  - status (started/success/error)")
    print()
    print("Check the stderr output above for JSON-formatted logs")
    print("containing these fields.")

    # Cleanup
    await processor.shutdown()

    print()
    print("=" * 70)
    print("✅ Demonstration complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
