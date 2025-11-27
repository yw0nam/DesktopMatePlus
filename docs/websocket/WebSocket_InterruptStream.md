# WebSocket: Interrupt Stream

The `interrupt_stream` message is sent by the client to interrupt an active response stream.

## Direction

Client -> Server

## Payload

```json
{
    "type": "interrupt_stream",
    "turn_id": "optional-turn-id"
}
```

### Fields

- `type` (string, required): Must be `"interrupt_stream"`.
- `turn_id` (string, optional): Specific turn ID to interrupt. If not provided, all active turns will be interrupted.

## Usage

The client can send this message to stop an ongoing agent response stream. This is useful for implementing user interruption functionality, such as when a user wants to ask a new question before the current response is complete.

## Example

```javascript
// Interrupt all active streams
function interruptAllStreams() {
    socket.send(JSON.stringify({
        type: 'interrupt_stream'
    }));
}

// Interrupt a specific turn
function interruptSpecificTurn(turnId) {
    socket.send(JSON.stringify({
        type: 'interrupt_stream',
        turn_id: turnId
    }));
}
```
