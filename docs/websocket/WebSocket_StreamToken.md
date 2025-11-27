# WebSocket: Stream Token

The `stream_token` message contains a chunk of the agent's text response. A complete response is assembled from one or more of these messages.

## Direction

Server -> Client

## Payload

```json
{
    "type": "stream_token",
    "chunk": "Hello! ",
    "node": "agent_response_node",
    "turn_id": "t1u2r3n4-i5d6-7890-1234-567890abcdef"
}
```

### Fields

- `type` (string, required): Must be `"stream_token"`.
- `chunk` (string, required): A piece of the agent's response. This can be a single word, a sentence fragment, or more.
- `node` (string, optional): Optional identifier for the processing node that generated this token.
- `turn_id` (string, required): The identifier for the current response turn, linking it to the initial `stream_start` message.

## Usage

The client should append the `chunk` from each `stream_token` message to its display to create the effect of the agent "typing" out its response in real-time. The stream of tokens for a single turn concludes when a `stream_end` message is received.

## Example

```javascript
// Assume 'currentResponseElement' is a reference to a <p> or <div> in the DOM

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'stream_token' && message.turn_id === currentTurnId) {
        // Append the new text chunk to the display
        currentResponseElement.textContent += message.chunk;
    }
};
```
