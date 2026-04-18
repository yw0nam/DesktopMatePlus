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
) -> TtsChunkMessage:
    """
    Always returns a single TtsChunkMessage.

    Behavior:
    - tts_enabled=True: calls generate_speech() via asyncio.to_thread()
    - tts_enabled=False: skips TTS API, audio_base64=None (normal state)
    - On failure: audio_base64=None, error logged backend-only — never raised

    Args:
        tts_service: TTS engine instance (TTSService ABC)
        mapper: EmotionMotionMapper for emotion → keyframes
        text: Text to synthesize
        emotion: Detected emotion tag (None → mapper returns default)
        sequence: Chunk order within turn (starts at 0)
        tts_enabled: False → skip TTS API entirely
        reference_id: Voice reference ID. None → engine default

    Returns:
        TtsChunkMessage with audio_base64=None on failure/disabled,
        keyframes always populated.
    """
    keyframes: list[TimelineKeyframe] = mapper.map(emotion)
    audio: str | None = None

    if tts_enabled:
        try:
            result = await to_thread(
                tts_service.generate_speech,
                text,
                reference_id,
                "base64",
                audio_format="wav",
            )
            if result is None:
                logger.error(f"TTS synthesis returned None for sequence {sequence}")
                audio = None
            else:
                audio = result
        except Exception as e:
            logger.error(f"TTS synthesis failed for sequence {sequence}: {e}")
            audio = None

    return TtsChunkMessage(
        sequence=sequence,
        text=text,
        audio_base64=audio,
        emotion=emotion,
        keyframes=keyframes,
    )
