"""External service clients."""

from src.services.health import HealthService, health_service
from src.services.screen_capture_service import (
    ScreenCaptureError,
    ScreenCaptureService,
    get_screen_capture_service,
)


# Global service storage
class _TTSService:
    """Container for global TTS engine instance."""

    tts_engine = None


class _VLMService:
    """Container for global VLM engine instance."""

    vlm_engine = None


_tts_service = _TTSService()
_vlm_service = _VLMService()

__all__ = [
    "HealthService",
    "health_service",
    "ScreenCaptureService",
    "ScreenCaptureError",
    "get_screen_capture_service",
    "_tts_service",
    "_vlm_service",
]
