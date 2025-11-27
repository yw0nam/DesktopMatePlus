# WebSocket: Switch Avatar Config

The `switch_avatar_config` message is sent by the client to switch to a different avatar configuration.

## Direction

Client -> Server

## Payload

```json
{
    "type": "switch_avatar_config",
    "file": "en_nuke_debate.yaml"
}
```

### Fields

- `type` (string, required): Must be `"switch_avatar_config"`.
- `file` (string, required): The filename of the configuration to switch to.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

The client sends this message to switch the avatar to a different configuration. The configuration file should be one of the files returned by the `fetch_avatar_configs` request. The server will respond with an `avatar_config_switched` message to confirm the switch.

## Example

```javascript
// Switch to a different avatar configuration
function switchAvatarConfig(configFilename) {
    socket.send(JSON.stringify({
        type: 'switch_avatar_config',
        file: configFilename
    }));
}

// Handle the confirmation
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'avatar_config_switched') {
        console.log('Avatar config switched to:', message.file);
        // Update UI to reflect the new configuration
        updateCurrentConfigDisplay(message.file);
    }
};

// Example: Switch to the debate persona
switchAvatarConfig('en_nuke_debate.yaml');
```
