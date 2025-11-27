# WebSocket: Stream End

The `stream_end` message signals that the agent has completed its response for the current turn.

## Direction

Server -> Client

## Payload

```json
{
    "type": "stream_end",
    "turn_id": "t1u2r3n4-i5d6-7890-1234-567890abcdef",
    "conversation_id": "c1l2i3e4n5t6-7890-1234-567890abcdef",
    "content": "The full response from the agent is included here for completeness."
}
```

### Fields

- `type` (string, required): Must be `"stream_end"`.
- `turn_id` (string, required): The identifier for the response turn that is now complete.
- `conversation_id` (string, required): The identifier for the client connection.
- `content` (string, required): The complete, final text of the agent's response for this turn. This is the aggregation of all `chunk` values from the preceding `stream_token` messages.

## Usage

Upon receiving this message, the client knows that no more `stream_token` or `tool_call` messages will be sent for this `turn_id`.

The client can use the `content` field to verify the integrity of the streamed response or to simply replace the assembled text, ensuring the final output is correct. This is also the time to hide any "agent is typing" indicators and save the final message to the chat history.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'stream_end' && message.turn_id === currentTurnId) {
        console.log(`Turn ${message.turn_id} has ended.`);

        // Hide the "typing" indicator
        hideAgentTypingIndicator();

        // Optionally, finalize the displayed text with the full content
        currentResponseElement.textContent = message.content;

        // Save the complete response to local chat history
        saveMessageToHistory('assistant', message.content);

        // Reset for the next turn
        currentTurnId = null;
    }
};
```
