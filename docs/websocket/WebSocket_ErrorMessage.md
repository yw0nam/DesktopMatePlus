# WebSocket: Error Message

The `error` message is sent by the server whenever an error occurs during WebSocket communication or agent processing.

## Direction

Server -> Client

## Payload

```json
{
    "type": "error",
    "code": 500,
    "error": "An unexpected error occurred while processing your request."
}
```

### Fields

- `type` (string, required): Must be `"error"`.
- `code` (integer, required): An error code, often corresponding to HTTP status codes (e.g., 400, 401, 500).
- `error` (string, required): A human-readable description of the error.

## Usage

When the client receives an `error` message, it should display an appropriate notification to the user. Depending on the error code, the client might need to take action, such as re-authorizing (on a 401) or simply reporting the failure.

The connection may or may not be closed by the server after sending an error, depending on the severity of the issue.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'error') {
        console.error(`Server error ${message.code}: ${message.error}`);

        // Display an error message in the UI
        showErrorNotification(message.error);

        if (message.code === 401) {
            // Handle unauthorized error, e.g., prompt for login
            handleUnauthorized();
        }
    }
};

socket.onerror = (error) => {
    // This handles lower-level transport errors, not application errors
    console.error('WebSocket transport error:', error);
    showErrorNotification('Connection to the server was lost.');
};
```
