# WebSocket: Fetch Backgrounds

The `fetch_backgrounds` message is sent by the client to request a list of available background images.

## Direction

Client -> Server

## Payload

```json
{
    "type": "fetch_backgrounds"
}
```

### Fields

- `type` (string, required): Must be `"fetch_backgrounds"`.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

The client sends this message to retrieve a list of all available background images that can be used in the desktop environment. The server will respond with a `background_files` message containing the list of available backgrounds.

## Example

```javascript
// Request available backgrounds
function fetchBackgrounds() {
    socket.send(JSON.stringify({
        type: 'fetch_backgrounds'
    }));
}

// Handle the response
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'background_files') {
        console.log('Available backgrounds:', message.files);
        // Populate UI with available backgrounds
        populateBackgroundSelector(message.files);
    };
};
```
