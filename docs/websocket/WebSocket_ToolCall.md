# WebSocket: Tool Call

The `tool_call` message is sent when the agent decides it needs to use a tool to answer a user's request.

## Direction

Server -> Client

## Payload

```json
{
    "type": "tool_call",
    "tool_name": "get_weather",
    "args": "{\"city\": \"London\"}",
    "node": "tool_execution_node"
}
```

### Fields

- `type` (string, required): Must be `"tool_call"`.
- `tool_name` (string, required): The name of the tool the agent is invoking.
- `args` (string, required): A JSON string containing the arguments for the tool.
- `node` (string, optional): Optional identifier for the processing node that initiated this tool call.

## Usage

This message is purely informational for the client. It allows the UI to display that the agent is performing an action, such as "Searching for the weather in London...".

The client does not need to act on this message, but it provides transparency into the agent's process. The result of this tool call will be sent in a subsequent `tool_result` message.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'tool_call' && message.turn_id === currentTurnId) {
        console.log(`Agent is calling tool: ${message.tool_name}`);

        // Display a message in the UI, e.g., "Using the get_weather tool..."
        showToolCallIndicator(message.tool_name, message.tool_input);
    }
};
```
