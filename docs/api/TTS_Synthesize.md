# TTS: Synthesize Speech

Updated: 2025-12-19

## 1. Synopsis

- **Purpose**: Convert text to speech audio
- **I/O**: `POST { text, reference_id?, output_format?, audio_format? }` → JSON or Binary audio

## 2. Core Logic

### Endpoint

`POST /v1/tts/synthesize`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Text to synthesize (min 1 char) |
| `reference_id` | string | No | Voice reference ID for cloning |
| `output_format` | string | No | `"base64"` (default) or `"bytes"` |
| `audio_format` | string | No | `"mp3"` (default) or `"wav"` |

### Response

**Success (200) - Base64 Format** (when `output_format="base64"`):

```json
{
  "audio_data": "base64_encoded_audio_string",
  "format": "base64"
}
```

**Success (200) - Binary Format** (when `output_format="bytes"`):

- **Content-Type**: `audio/mpeg` (for mp3) or `audio/wav` (for wav)
- **Body**: Raw binary audio data

**Errors**: `422` (missing/empty text), `401` (unauthorized), `500` (synthesis failed)

## 3. Usage

### Example 1: Base64 Format (JSON Response)

```bash
curl -X POST "http://127.0.0.1:5500/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{ "text": "Hello, world!", "output_format": "base64", "audio_format": "mp3" }'
```

### Example 2: Binary Format (Raw Audio Response)

```bash
curl -X POST "http://127.0.0.1:5500/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{ "text": "Hello, world!", "output_format": "bytes", "audio_format": "mp3" }' \
  --output audio.mp3
```

---

## Appendix

### A. JavaScript Playback Example (Base64)

```javascript
fetch('http://127.0.0.1:5500/v1/tts/synthesize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: 'Hello!',
    output_format: 'base64',
    audio_format: 'mp3'
  })
})
.then(res => res.json())
.then(data => {
  const audio = new Audio(`data:audio/mpeg;base64,${data.audio_data}`);
  audio.play();
});
```

### B. Unity Example (Binary Response)

```csharp
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;

public class TTSClient : MonoBehaviour
{
    IEnumerator GetTTSAudio(string text)
    {
        string url = "http://127.0.0.1:5500/v1/tts/synthesize";

        // Create JSON request body
        string jsonData = JsonUtility.ToJson(new TTSRequest {
            text = text,
            output_format = "bytes",
            audio_format = "mp3"
        });

        // Use UnityWebRequestMultimedia for audio
        using (UnityWebRequest www = UnityWebRequest.Post(url, jsonData, "application/json"))
        {
            // Set to download audio
            www.downloadHandler = new DownloadHandlerAudioClip(url, AudioType.MPEG);

            yield return www.SendWebRequest();

            if (www.result == UnityWebRequest.Result.Success)
            {
                AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
                AudioSource.PlayClipAtPoint(clip, Camera.main.transform.position);
            }
        }
    }

    [System.Serializable]
    class TTSRequest
    {
        public string text;
        public string output_format;
        public string audio_format;
    }
}
```

### C. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
- [TTS Ready Chunk (WebSocket)](../websocket/WebSocket_TTSReadyChunk.md)

---

## Notes

### Format Selection Guide

- **MP3 (Recommended for bytes)**: Compressed format, smaller file size (~10x smaller than WAV), ideal for network transmission and Unity/mobile apps
- **WAV**: Uncompressed format, larger file size, higher quality, better for base64 embedding in HTML

### Backward Compatibility

- Old clients using `output_format="base64"` without `audio_format` will continue to work (defaults to mp3)
- The base64 format still returns JSON, maintaining compatibility with existing JavaScript integrations
