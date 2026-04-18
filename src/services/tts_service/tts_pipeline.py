"""TTS synthesis pipeline — text + emotion → TtsChunkMessage.

synthesize_chunk() never raises. All errors are logged to backend only.
"""

import base64
import struct
from asyncio import to_thread

from src.core.logger import logger
from src.models.websocket import TimelineKeyframe, TtsChunkMessage
from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper
from src.services.tts_service.service import TTSService
from src.services.tts_service.viseme_mapper import VisemeMapper


def wav_duration(data: bytes | None) -> float:
    """Calculate duration in seconds from raw WAV bytes.

    Returns 0.0 on invalid input or parse failure.
    """
    if not data or len(data) < 44:
        return 0.0
    try:
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return 0.0
        # Parse fmt chunk: channels at offset 22, sample_rate at 24, bits at 34
        channels = struct.unpack_from("<H", data, 22)[0]
        sample_rate = struct.unpack_from("<I", data, 24)[0]
        bits_per_sample = struct.unpack_from("<H", data, 34)[0]
        if sample_rate == 0 or channels == 0 or bits_per_sample == 0:
            return 0.0
        # Find data chunk size at offset 40
        data_size = struct.unpack_from("<I", data, 40)[0]
        bytes_per_sample = bits_per_sample // 8
        return data_size / (sample_rate * channels * bytes_per_sample)
    except (struct.error, ZeroDivisionError):
        return 0.0


async def synthesize_chunk(
    tts_service: TTSService,
    mapper: EmotionMotionMapper,
    text: str,
    emotion: str | None,
    sequence: int,
    tts_enabled: bool = True,
    reference_id: str | None = None,
    viseme_mapper: VisemeMapper | None = None,
) -> TtsChunkMessage:
    """Synthesize a text chunk into audio + animation keyframes.

    Always returns a TtsChunkMessage, never raises.
    When viseme_mapper is provided and TTS succeeds, generates lip-sync
    keyframes merged with emotion targets. Falls back to emotion-only
    keyframes on any failure.
    """
    # 1. Generate emotion keyframes (always)
    keyframes: list[TimelineKeyframe] = mapper.map(emotion)

    audio_base64: str | None = None

    if not tts_enabled:
        return TtsChunkMessage(
            sequence=sequence,
            text=text,
            audio_base64=None,
            emotion=emotion,
            keyframes=keyframes,
        )

    # 2. Generate speech as raw bytes first (for duration calculation)
    try:
        audio_bytes: bytes | None = await to_thread(
            tts_service.generate_speech,
            text,
            reference_id,
            "bytes",
            audio_format="wav",
        )
    except Exception:
        logger.opt(exception=True).warning("[TTS] generate_speech failed")
        audio_bytes = None

    # 3. If audio succeeded, compute duration and generate visemes
    if audio_bytes and isinstance(audio_bytes, bytes):
        audio_base64 = base64.b64encode(audio_bytes).decode("ascii")

        if viseme_mapper is not None:
            duration = wav_duration(audio_bytes)
            if duration > 0:
                # Extract emotion targets from last emotion keyframe
                emotion_targets: dict[str, float] | None = None
                if keyframes:
                    last_kf = keyframes[-1]
                    if isinstance(last_kf, dict) and "targets" in last_kf:
                        targets_value = last_kf["targets"]
                        if isinstance(targets_value, dict):
                            emotion_targets = targets_value

                try:
                    viseme_keyframes = viseme_mapper.generate(
                        text, duration, emotion_targets
                    )
                except Exception:
                    logger.opt(exception=True).warning(
                        "[Viseme] generate failed, falling back to emotion keyframes"
                    )
                    viseme_keyframes = []
                if viseme_keyframes:
                    keyframes = viseme_keyframes
    else:
        logger.warning(
            f"[TTS] generate_speech returned no audio for sequence {sequence}"
        )

    return TtsChunkMessage(
        sequence=sequence,
        text=text,
        audio_base64=audio_base64,
        emotion=emotion,
        keyframes=keyframes,
    )
