# WebSocket: Tool Result

The `tool_result` message provides the output from a tool that the agent invoked.

## Direction

Server -> Client

## Payload

```json
{
    "type": "tool_result",
    "result": "{\"temperature\": \"15°C\", \"condition\": \"Cloudy\"}",
    "node": "tool_execution_node"
}
```

### Fields

- `type` (string, required): Must be `"tool_result"`.
- `result` (string, required): A JSON string containing the data returned by the tool.
- `node` (string, optional): Optional identifier for the processing node that executed the tool.

## Usage

Like the `tool_call` message, this is primarily for informational purposes. It allows the UI to show the data the agent is working with. For example, you could display a small card with the weather information that was fetched.

After receiving the tool result, the agent will continue processing and will typically generate more `stream_token` messages to formulate its final answer based on the tool's output.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'tool_result' && message.turn_id === currentTurnId) {
        console.log(`Agent received result from tool: ${message.tool_name}`);

        // Hide the specific tool call indicator
        hideToolCallIndicator(message.tool_name);

        // Optionally, display the result in a structured way
        displayToolResult(message.tool_name, message.tool_output);
    }
};
```
