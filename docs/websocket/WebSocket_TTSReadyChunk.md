# WebSocket: TTS Ready Chunk

The `tts_ready_chunk` message is sent by the server to indicate that a chunk of text is ready for Text-to-Speech synthesis.

## Direction

Server -> Client

## Payload

```json
{
    "type": "tts_ready_chunk",
    "chunk": "Text content ready for TTS",
    "emotion": "optional-emotion"
}
```

### Fields

- `type` (string, required): Must be `"tts_ready_chunk"`.
- `chunk` (string, required): The text content that is ready for TTS synthesis.
- `emotion` (string, optional): Optional emotion indicator for the TTS synthesis.

## Usage

This message is sent by the server during streaming responses to indicate portions of text that are ready to be synthesized into speech. The client can use this to provide real-time TTS functionality, synthesizing text chunks as they become available rather than waiting for the complete response.

## Example

```javascript
socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'tts_ready_chunk') {
        // Synthesize this chunk of text to speech
        synthesizeSpeech(message.chunk, message.emotion);
    }
};
```
