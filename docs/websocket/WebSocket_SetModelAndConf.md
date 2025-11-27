# WebSocket: Set Model And Conf

The `set_model_and_conf` message is sent by the server to provide Live2D model and configuration information to the client.

## Direction

Server -> Client

## Payload

```json
{
    "type": "set_model_and_conf",
    "model_info": {
        "model_path": "/models/mao_pro/mao_pro.model3.json",
        "texture_path": "/models/mao_pro/textures/",
        "expressions": ["happy", "sad", "angry", "surprised"],
        "motions": ["idle", "wave", "nod"]
    },
    "conf_name": "Mao Pro",
    "conf_uid": "mao-pro-001",
    "client_uid": "client-123-456"
}
```

### Fields

- `type` (string, required): Must be `"set_model_and_conf"`.
- `model_info` (object, required): Live2D model information containing paths and available expressions/motions.
- `conf_name` (string, required): The display name of the configuration.
- `conf_uid` (string, required): Unique identifier for the configuration.
- `client_uid` (string, required): Unique identifier for the client.
- `id` (string, optional): Message ID for tracking purposes.
- `timestamp` (float, optional): Unix timestamp of the message.

## Usage

This message is sent by the server to provide the client with all necessary information to load and configure a Live2D model. The client should use this information to initialize or update the Live2D renderer with the correct model, textures, expressions, and motions.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'set_model_and_conf') {
        console.log('Received model configuration:', message.conf_name);

        // Initialize or update the Live2D model
        const modelConfig = {
            modelInfo: message.model_info,
            configName: message.conf_name,
            configUid: message.conf_uid,
            clientUid: message.client_uid
        };

        // Load the Live2D model with the provided configuration
        loadLive2DModel(modelConfig);

        // Update UI to show current configuration
        document.getElementById('model-name').textContent = message.conf_name;
    }
};

function loadLive2DModel(config) {
    // Implementation depends on your Live2D SDK integration
    live2dManager.loadModel(config.modelInfo.model_path);
    live2dManager.setExpressions(config.modelInfo.expressions);
    live2dManager.setMotions(config.modelInfo.motions);
}
```
