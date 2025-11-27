# POST /v1/tts/synthesize

Synthesize text into speech and return the audio data.

## Overview

This endpoint takes a string of text and converts it into spoken audio using the configured Text-to-Speech (TTS) engine. It returns a JSON response containing the audio data and format information.

## Request

### Method

`POST`

### URL

`/v1/tts/synthesize`

### Headers

- `Authorization`: `Bearer <Your-Auth-Token>` (Optional)
- `Content-Type`: `application/json`

### Body

A JSON object containing the text to be synthesized and optional parameters.

```json
{
    "text": "Hello, world! This is a test of the text-to-speech system.",
    "reference_id": "optional_voice_id",
    "output_format": "base64"
}
```

- `text` (string, required): The text to synthesize into speech. Must be at least 1 character long.
- `reference_id` (string, optional): Reference voice ID for voice cloning (provider-specific).
- `output_format` (string, optional): Output format for audio data. Can be "bytes" or "base64". Defaults to "base64".

## Response

### Success (200 OK)

Returns a JSON object containing the synthesized audio data.

- **Content-Type**: `application/json`

```json
{
    "audio_data": "base64_encoded_audio_string",
    "format": "base64"
}
```

- `audio_data` (string): The audio data, encoded as specified in the request's `output_format`.
- `format` (string): The format of the audio data (e.g., "base64" or "bytes").

### Error

- **422 Unprocessable Entity**: If the `text` field is missing or empty in the request body.
- **401 Unauthorized**: If the authorization token is missing or invalid.
- **500 Internal Server Error**: If the TTS service fails to synthesize the audio.

## Example

### cURL

This example fetches the JSON response containing the base64-encoded audio data.

```bash
curl -X POST "http://127.0.0.1:5500/v1/tts/synthesize" \
-H "Content-Type: application/json" \
-d '{"text": "This is a demonstration of the TTS API.", "output_format": "base64"}'
```

The response will be a JSON object with `audio_data` containing the base64-encoded audio.

### JavaScript (Fetch API)

This example demonstrates how to fetch the JSON response, decode the base64 audio data, and play it using the Web Audio API.

```javascript
const textToSynthesize = "Hello from the Web Audio API!";

fetch('http://127.0.0.1:5500/v1/tts/synthesize', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        text: textToSynthesize,
        output_format: 'base64'
    }),
})
.then(response => {
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    return response.json();
})
.then(data => {
    // Decode base64 audio data
    const audioData = atob(data.audio_data);
    const arrayBuffer = new ArrayBuffer(audioData.length);
    const uint8Array = new Uint8Array(arrayBuffer);
    for (let i = 0; i < audioData.length; i++) {
        uint8Array[i] = audioData.charCodeAt(i);
    }

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    return audioContext.decodeAudioData(arrayBuffer);
})
.then(audioBuffer => {
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    source.start(0);
})
.catch(error => console.error('Error:', error));
```
