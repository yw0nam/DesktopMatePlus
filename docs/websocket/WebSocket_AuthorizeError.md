# WebSocket: Authorize Error

The `authorize_error` message is sent by the server when authorization of a WebSocket connection fails.

## Direction

Server -> Client

## Payload

```json
{
    "type": "authorize_error",
    "error": "Error message describing what went wrong"
}
```

### Fields

- `type` (string, required): Must be `"authorize_error"`.
- `error` (string, required): Description of the authorization error.

## Usage

This message is sent by the server when authorization fails. The client should handle this error appropriately, possibly by displaying an error message to the user or attempting to re-authorize with a different token.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'authorize_error') {
        console.error('Authorization failed:', message.error);
        // Handle authorization failure
        showErrorToUser(message.error);
        socket.close();
    }
};
```
