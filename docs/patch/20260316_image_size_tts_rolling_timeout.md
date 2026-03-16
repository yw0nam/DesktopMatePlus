# Patch Notes: Image Size Limit & TTS Rolling Timeout

Date: 2026-03-16

## Overview

Three bugs found during real E2E testing with `examples/realtime_tts_streaming_demo.py`:

1. WebSocket connection silently dropped when sending large images (>10MB JSON body)
2. TTS chunks 2+ dropped when multiple sentences exceeded the global 10s barrier timeout
3. `img.model_dump()` called on already-serialized plain dict — would raise `AttributeError` at runtime

## Bug Fixes

### Fix 1: Image Size Enforcement (client + server)

**Root cause**: A 27MB PNG encodes to ~36MB base64 JSON, exceeding Uvicorn's default 10MB WebSocket frame limit. The server closed the connection before parsing the message, with no error log.

**Server** (`src/models/websocket.py`):
- Added `field_validator` on `ImageContent.image_url`: rejects base64 data URLs exceeding 6MB (≈4.5MB binary) with a clear `ValidationError` → client receives `error` event instead of silent disconnect.

**Client** (`examples/realtime_tts_streaming_demo.py`):
- Added `_resize_to_limit()`: auto-resizes images over 4MB using Pillow (JPEG, 75% scale steps, RGBA→RGB conversion).
- `_load_image_as_base64()` now calls resize automatically and logs the resulting size.

**Constraints**:

| Limit | Value | Notes |
|-------|-------|-------|
| Max binary per image | 4 MB | Applied at client before encoding |
| Max base64 per image | 6 MB | Enforced by server `ImageContent` validator |

### Fix 2: TTS Barrier — Rolling Inactivity Timeout

**Root cause**: `asyncio.wait_for(gather(*tts_tasks), timeout=10s)` used a single global timeout. With 5 TTS chunks at ~4.5s each (sequential), the barrier fired at 10s, dropping chunks 2–5.

**Change** (`src/services/websocket_service/message_processor/processor.py`):

Old behavior:
```
asyncio.wait_for(gather(tasks...), timeout=10s)  ← single global deadline
```

New behavior (rolling):
```
while pending:
    done, pending = asyncio.wait(pending, timeout=30s, FIRST_COMPLETED)
    if not done:
        cancel remaining → log warning → break
    # timer resets implicitly on each chunk completion
```

The timer resets each time any TTS task completes. Only fires if no task completes within `tts_barrier_timeout_seconds`.

**Default changed** (`src/configs/settings.py`): `10.0s` → `30.0s`

```yaml
# yaml_files/main.yml
websocket:
  tts_barrier_timeout_seconds: 30.0  # was 10.0 — now per-chunk inactivity window
```

### Fix 3: `img.model_dump()` on plain dict

**Root cause**: `handle_chat_message` received `validated_message_data` (result of `ChatMessage.model_dump()`), so `images` was already `list[dict]`. Calling `.model_dump()` on a dict raises `AttributeError`.

**Change** (`src/services/websocket_service/manager/handlers.py`):

```python
# Before
content.extend([img.model_dump() for img in images])

# After
content.extend(images)
```

## Files Changed

| File | Change |
|------|--------|
| `src/models/websocket.py` | Added `field_validator` on `ImageContent.image_url` for size limit |
| `src/services/websocket_service/message_processor/processor.py` | `_wait_for_tts_tasks()` — rolling timeout via `asyncio.wait` loop |
| `src/configs/settings.py` | `tts_barrier_timeout_seconds` default: `10.0` → `30.0`, description updated |
| `src/services/websocket_service/manager/handlers.py` | `content.extend(images)` — removed spurious `.model_dump()` |
| `examples/realtime_tts_streaming_demo.py` | Added `_resize_to_limit()`, auto-resize in `_load_image_as_base64()` |
| `tests/core/test_tts_barrier.py` | Updated timeout test for rolling behavior |
| `tests/models/test_websocket_models.py` | Added `TestImageContentValidation` (3 cases) |
| `docs/websocket/WebSocket_ChatMessage.md` | Added image size constraints section |
| `docs/websocket/WEBSOCKET_API_GUIDE.md` | Updated `tts_barrier_timeout_seconds` to `30.0` |
