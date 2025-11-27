# WebSocket: Fetch Avatar Configs

The `fetch_avatar_configs` message is sent by the client to request a list of available avatar configurations.

## Direction

Client -> Server

## Payload

```json
{
    "type": "fetch_avatar_configs"
}
```

### Fields

- `type` (string, required): Must be `"fetch_avatar_configs"`.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

The client sends this message to retrieve a list of all available avatar (character) configurations. These configurations define different personas, behaviors, and settings for the desktop assistant. The server will respond with an `avatar_config_files` message containing the list of available configurations.

## Example

```javascript
// Request available avatar configurations
function fetchAvatarConfigs() {
    socket.send(JSON.stringify({
        type: 'fetch_avatar_configs'
    }));
}

// Handle the response
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'avatar_config_files') {
        console.log('Available avatar configs:', message.configs);
        // Populate UI with available configurations
        message.configs.forEach(config => {
            console.log(`Filename: ${config.filename}, Name: ${config.name}`);
        });
    }
};
```
