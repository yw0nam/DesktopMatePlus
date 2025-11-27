# WebSocket: Authorize

The `authorize` message is sent by the client to authenticate its WebSocket connection.

## Direction

Client -> Server

## Payload

```json
{
    "type": "authorize",
    "token": "your-secret-auth-token"
}
```

### Fields

- `type` (string, required): Must be `"authorize"`.
- `token` (string, required): The authentication token for the user or client. For development, this can be any non-empty string.

## Usage

The client **must** send this message immediately after the WebSocket connection is established. The server will not process any other messages from the client until it has been successfully authorized.

Upon successful authorization, the server will respond with an `authorize_success` message.

## Example

```javascript
const socket = new WebSocket('ws://127.0.0.1:8000/api/v1/ws/chat');

socket.onopen = () => {
    console.log('WebSocket connection established.');

    const authMessage = {
        type: 'authorize',
        token: 'dev-token-123'
    };

    socket.send(JSON.stringify(authMessage));
};

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'authorize_success') {
        console.log('Authorization successful! Connection ID:', message.connection_id);
        // Now we can send chat messages
    }
};
};
```
