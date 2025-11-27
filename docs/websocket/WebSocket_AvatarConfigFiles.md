# WebSocket: Avatar Config Files

The `avatar_config_files` message is sent by the server in response to a `fetch_avatar_configs` request, containing a list of available avatar configurations.

## Direction

Server -> Client

## Payload

```json
{
    "type": "avatar_config_files",
    "configs": [
        {
            "filename": "en_nuke_debate.yaml",
            "name": "Nuke Debate"
        },
        {
            "filename": "en_unhelpful_ai.yaml",
            "name": "Unhelpful AI"
        }
    ]
}
```

### Fields

- `type` (string, required): Must be `"avatar_config_files"`.
- `configs` (array of objects, required): List of available avatar configurations.
  - `filename` (string, required): The configuration filename.
  - `name` (string, required): The display name of the configuration.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

This message is sent by the server in response to a `fetch_avatar_configs` request. The client can use this list to populate a character/persona selector UI, allowing users to switch between different avatar configurations.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'avatar_config_files') {
        console.log('Available avatar configs:', message.configs);

        // Populate a dropdown with avatar configuration options
        const configSelector = document.getElementById('avatar-config-selector');
        configSelector.innerHTML = '';

        message.configs.forEach(config => {
            const option = document.createElement('option');
            option.value = config.filename;
            option.textContent = config.name;
            configSelector.appendChild(option);
        });
    }
};
```
