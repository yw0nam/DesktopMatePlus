# TTS Service — Patterns & Conventions

Updated: 2026-03-25

- **`EmotionMotionMapper`** is a standalone service initialized in lifespan via `initialize_emotion_motion_mapper()`. It reads `emotion_motion_map` from `yaml_files/tts_rules.yml` and maps emotion strings → `list[TimelineKeyframe]`.
- **`TimelineKeyframe` type:** `dict[str, float | dict[str, float]]` — e.g., `{"duration": 0.3, "targets": {"happy": 1.0}}`. Replaces the old `motion_name`/`blendshape_name` fields.
- **`synthesize_chunk()`** in `tts_pipeline.py`: always returns a `TtsChunkMessage` (never raises). If TTS fails or is disabled, `audio_base64=None`; `keyframes` is always populated from the mapper.
- **Audio format:** TTS service is called with `audio_format="wav"`. Encoded as base64 in `TtsChunkMessage.audio_base64`.
- **Service init order in lifespan:** TTS → EmotionMotionMapper → MongoDB (checkpointer) → Agent → LTM → Channel → Sweep.
