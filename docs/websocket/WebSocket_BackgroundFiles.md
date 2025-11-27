# WebSocket: Background Files

The `background_files` message is sent by the server in response to a `fetch_backgrounds` request, containing a list of available background images.

## Direction

Server -> Client

## Payload

```json
{
    "type": "background_files",
    "files": ["background1.jpg", "background2.png", "nature_scene.jpg"]
}
```

### Fields

- `type` (string, required): Must be `"background_files"`.
- `files` (array of strings, required): List of available background filenames.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

This message is sent by the server in response to a `fetch_backgrounds` request. The client can use this list to populate a background selector UI, allowing users to choose and switch between different desktop backgrounds.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'background_files') {
        console.log('Available backgrounds:', message.files);

        // Populate a dropdown or grid with background options
        const backgroundSelector = document.getElementById('background-selector');
        backgroundSelector.innerHTML = '';

        message.files.forEach(filename => {
            const option = document.createElement('option');
            option.value = filename;
            option.textContent = filename;
            backgroundSelector.appendChild(option);
        });
    }
};
```
