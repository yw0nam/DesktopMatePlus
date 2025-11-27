# WebSocket: Ping

The `ping` message is sent by the server to check if the client is still connected and responsive.

## Direction

Server -> Client

## Payload

```json
{
    "type": "ping"
}
```

### Fields

- `type` (string, required): Must be `"ping"`.

## Usage

The server sends this message periodically to implement a heartbeat mechanism. The client should respond with a `pong` message to indicate it is still active. If the server doesn't receive a timely `pong` response, it may close the connection.

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
