"""External service clients."""

from src.services.health import HealthService, health_service
from src.services.screen_capture_service import (
    ScreenCaptureError,
    ScreenCaptureService,
    get_screen_capture_service,
)
from src.services.tts_service import (
    TTSClient,
    TTSService,
    get_tts_client,
    initialize_tts_client,
    synthesize_speech,
)

__all__ = [
    "HealthService",
    "health_service",
    "ScreenCaptureService",
    "ScreenCaptureError",
    "get_screen_capture_service",
    "TTSClient",
    "TTSService",
    "get_tts_client",
    "initialize_tts_client",
    "synthesize_speech",
]
