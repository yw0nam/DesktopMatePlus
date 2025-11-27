# WebSocket: Stream Start

The `stream_start` message signals the beginning of a new response "turn" from the agent.

## Direction

Server -> Client

## Payload

```json
{
    "type": "stream_start",
    "turn_id": "t1u2r3n4-i5d6-7890-1234-567890abcdef",
    "conversation_id": "c1l2i3e4n5t6-7890-1234-567890abcdef"
}
```

### Fields

- `type` (string, required): Must be `"stream_start"`.
- `turn_id` (string, required): A unique identifier for this specific agent response turn. A turn consists of all messages from one `stream_start` to the corresponding `stream_end`.
- `conversation_id` (string, required): The identifier for the client connection.

## Usage

When the client receives this message, it should prepare to receive a sequence of `stream_token`, `tool_call`, and `tool_result` messages. This message provides the `turn_id` that will be associated with all subsequent messages in this turn.

This is a good time to update the UI to indicate that the agent is generating a response.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'stream_start') {
        console.log(`New turn started with ID: ${message.turn_id}`);
        // Store the turn_id and conversation_id for context
        currentTurnId = message.turn_id;
        currentConversationId = message.conversation_id;

        // Show a "typing" indicator in the UI
        showAgentTypingIndicator();
    }
};
```
