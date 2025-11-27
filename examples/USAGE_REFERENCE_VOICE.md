# Using Reference Voice (ナツメ) in TTS Streaming Demo

## ✨ New Feature: Reference Voice Support

The demo now supports specifying a reference voice ID for Fish Speech TTS. The default voice is **ナツメ**.

## Usage

### Default (ナツメ voice)
```bash
uv run python examples/realtime_tts_streaming_demo.py
```

### Custom reference voice
```bash
uv run python examples/realtime_tts_streaming_demo.py --reference-id "ナツメ"
```

### Full example with all options
```bash
uv run python examples/realtime_tts_streaming_demo.py \
    --message "I make this illustration, that will be your appearance of you. Is it your type?" \
    --reference-id "ナツメ" \
    --image "https://www.1999.co.jp/itbig67/10676525a.jpg" \
    --output ./my_tts_files
```

## What Changed

### 1. Added `reference_id` parameter to initialization
```python
demo = RealtimeTTSDemo(
    websocket_url="ws://localhost:8000/v1/chat/stream",
    tts_url="http://localhost:8000/v1/tts/synthesize",
    reference_id="ナツメ",  # ← New parameter
)
```

### 2. Included in TTS API requests
```python
payload = {
    "text": text,
    "output_format": "base64",
    "reference_id": self.reference_id,  # ← Sent to API
}
```

### 3. Command-line argument
```bash
--reference-id REFERENCE_ID
    Reference voice ID for TTS (default: ナツメ)
```

## Output

When you run the demo, you'll see:
```
📁 Output directory: /path/to/tts_output
🎙️  Reference voice: ナツメ
```

All generated WAV files will use the ナツメ voice for synthesis.

## Testing

Test the TTS API directly:
```bash
uv run python examples/test_tts_api.py
```

This will:
- Test TTS API with ナツメ voice
- Generate `test_tts_output.wav`
- Verify the reference voice is working

## Fish Speech Reference Voices

Fish Speech supports various reference voices. The `reference_id` parameter allows you to select which voice to use for synthesis. Common voices include:
- ナツメ (default in this demo)
- Other voices configured in your Fish Speech setup

Check your Fish Speech configuration for available reference voices.
