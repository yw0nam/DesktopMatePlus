# WebSocket: Pong

The `pong` message is sent by the client in response to a server `ping` message for heartbeat functionality.

## Direction

Client -> Server

## Payload

```json
{
    "type": "pong"
}
```

### Fields

- `type` (string, required): Must be `"pong"`.

## Usage

The client should respond to server `ping` messages with a `pong` message to maintain the WebSocket connection. This implements a heartbeat mechanism to detect connection issues.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'ping') {
        // Respond with pong to keep connection alive
        socket.send(JSON.stringify({ type: 'pong' }));
    }
};
```
