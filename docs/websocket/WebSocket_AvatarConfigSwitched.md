# WebSocket: Avatar Config Switched

The `avatar_config_switched` message is sent by the server to confirm that the avatar configuration has been successfully switched.

## Direction

Server -> Client

## Payload

```json
{
    "type": "avatar_config_switched",
    "file": "en_nuke_debate.yaml"
}
```

### Fields

- `type` (string, required): Must be `"avatar_config_switched"`.
- `file` (string, required): The filename of the configuration that was switched to.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

This message is sent by the server in response to a successful `switch_avatar_config` request. The client can use this confirmation to update the UI and reflect the current active configuration.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'avatar_config_switched') {
        console.log('Avatar config successfully switched to:', message.file);

        // Update the UI to reflect the new active configuration
        document.getElementById('current-config').textContent = message.file;

        // Show a success notification
        showNotification(`Switched to configuration: ${message.file}`);
    }
};
```
