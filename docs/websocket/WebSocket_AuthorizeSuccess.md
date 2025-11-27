# WebSocket: Authorize Success

The `authorize_success` message is sent by the server to confirm successful authorization of a WebSocket connection.

## Direction

Server -> Client

## Payload

```json
{
    "type": "authorize_success",
    "connection_id": "uuid-string"
}
```

### Fields

- `type` (string, required): Must be `"authorize_success"`.
- `connection_id` (string, required): A unique UUID identifier for this connection.

## Usage

This message is sent by the server immediately after successful authorization. The client should store the `connection_id` for tracking purposes. After receiving this message, the client can begin sending chat messages.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'authorize_success') {
        console.log('Authorization successful! Connection ID:', message.connection_id);
        // Store connection ID for future reference
        currentConnectionId = message.connection_id;
        // Now we can send chat messages
    }
};
```
