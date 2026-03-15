# Patch Notes: TTS Flow Refactor

Date: 2026-03-15
Branch: `feature/tts-flow-refactor`

## Overview

Backend now handles TTS synthesis internally. Unity (Dumb UI) receives pre-synthesized audio + motion data via `tts_chunk` events — no synthesis logic on the client.

## Breaking Changes

### WebSocket Protocol

| Before | After |
|--------|-------|
| `tts_ready_chunk` event (text only) | `tts_chunk` event (audio + motion) |
| Client synthesizes audio from text | Client plays pre-synthesized MP3 base64 |
| No motion data | `motion_name` + `blendshape_name` in every chunk |

**`chat_message` new optional fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `tts_enabled` | `true` | `false` = skip audio synthesis; still receive `tts_chunk` with motion |
| `reference_id` | `null` | Voice reference ID; `null` = engine default |

### REST API

| Before | After |
|--------|-------|
| `POST /v1/tts/synthesize` | ~~removed~~ |
| _(none)_ | `GET /v1/tts/voices` → `{"voices": [...]}` |

## New Features

### `tts_chunk` WebSocket Event

```json
{
  "type": "tts_chunk",
  "sequence": 0,
  "text": "Hello, how are you?",
  "audio_base64": "//NExAA...",
  "emotion": "joyful",
  "motion_name": "happy_idle",
  "blendshape_name": "smile"
}
```

- `audio_base64` is `null` when `tts_enabled=false` or synthesis fails
- `motion_name` / `blendshape_name` always populated — use for avatar animation even when audio is null
- Guaranteed to arrive before `stream_end` (TTS barrier)

### TTS Barrier

`stream_end` is sent only after all `tts_chunk` tasks complete (max 10s timeout). No more race condition between audio delivery and turn completion. Timeout is configurable:

```yaml
# yaml_files/main.yml
websocket:
  tts_barrier_timeout_seconds: 10.0
```

### EmotionMotionMapper

Emotion keyword → `(motion_name, blendshape_name)` configured in `yaml_files/tts_rules.yml`:

```yaml
emotion_motion_map:
  joyful:  { motion: "happy_idle",   blendshape: "smile" }
  default: { motion: "neutral_idle", blendshape: "neutral" }
```

### GET /v1/tts/voices

Returns available voice IDs for the configured TTS engine.

```bash
curl http://127.0.0.1:5500/v1/tts/voices
# {"voices": ["aria", "alice"]}
# 503 if TTS service not initialized
```

## Unity Integration Guide

```csharp
// Handle tts_chunk
case "tts_chunk":
    var seq = msg["sequence"].GetInt();
    var motionName = msg["motion_name"].GetString();
    var blendshape = msg["blendshape_name"].GetString();
    var audioB64 = msg["audio_base64"]?.GetString();  // may be null

    avatar.PlayMotion(motionName);
    avatar.SetBlendshape(blendshape);

    if (audioB64 != null) {
        var audioBytes = Convert.FromBase64String(audioB64);
        audioQueue.Enqueue(seq, audioBytes);  // MP3 format
    }
    break;
```

## Internal Architecture

```
EventHandler._process_token_event()
  → asyncio.create_task(_synthesize_and_send())  ← per sentence, parallel
      → synthesize_chunk()                         ← asyncio.to_thread(generate_speech)
          → TtsChunkMessage                        ← always returned, never raises
              → _put_event(turn_id, tts_chunk)

stream_end branch:
  _wait_for_token_queue()
  → _wait_for_tts_tasks()  ← asyncio.wait_for(..., timeout=10s)
  → _put_event(stream_end)
```

## Files Changed

| File | Change |
|------|--------|
| `src/models/websocket.py` | Added `TtsChunkMessage`, `tts_enabled`/`reference_id` to `ChatMessage`; removed `TTSReadyChunkMessage` |
| `src/services/tts_service/emotion_motion_mapper.py` | New: EmotionMotionMapper |
| `src/services/tts_service/tts_pipeline.py` | New: `synthesize_chunk()` |
| `src/services/tts_service/service.py` | Added `list_voices()` abstract method |
| `src/services/tts_service/vllm_omni.py` | Added `list_voices()` with directory scan + cache |
| `src/services/tts_service/fish_speech.py` | Added `list_voices() → []` |
| `src/models/tts.py` | Replaced with `VoicesResponse` only |
| `src/api/routes/tts.py` | Replaced with `GET /v1/tts/voices` only |
| `src/services/service_manager.py` | Added `initialize_emotion_motion_mapper()` |
| `src/services/websocket_service/message_processor/models.py` | Added `tts_tasks`, `tts_sequence`, `tts_enabled`, `reference_id` to `ConversationTurn` |
| `src/services/websocket_service/message_processor/processor.py` | Added `tts_service`/`mapper` params, `is_connection_closing()`, `_wait_for_tts_tasks()` |
| `src/services/websocket_service/message_processor/event_handlers.py` | Added `_synthesize_and_send()`, replaced `_build_tts_event()` with `create_task` pattern |
| `src/services/websocket_service/manager/handlers.py` | Inject services, extract `tts_enabled`/`reference_id` |
| `src/configs/settings.py` | Added `tts_barrier_timeout_seconds` to `WebSocketConfig` |
| `yaml_files/main.yml` | Added `tts_barrier_timeout_seconds: 10.0` |
| `yaml_files/tts_rules.yml` | Added `emotion_motion_map` section |
| `docs/api/TTS_Synthesize.md` | **Deleted** |
