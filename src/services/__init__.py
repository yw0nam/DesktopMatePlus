"""External service clients."""

from src.services.health import HealthService, health_service
from src.services.screen_capture_service import (
    ScreenCaptureError,
    ScreenCaptureService,
    get_screen_capture_service,
)
from src.services.service_manager import (
    get_agent_service,
    get_emotion_motion_mapper,
    get_ltm_service,
    get_stm_service,
    get_tts_service,
    initialize_agent_service,
    initialize_emotion_motion_mapper,
    initialize_ltm_service,
    initialize_services,
    initialize_stm_service,
    initialize_tts_service,
)

__all__ = [
    "HealthService",
    "health_service",
    "ScreenCaptureService",
    "ScreenCaptureError",
    "get_screen_capture_service",
    "initialize_services",
    "initialize_tts_service",
    "initialize_agent_service",
    "initialize_stm_service",
    "initialize_ltm_service",
    "initialize_emotion_motion_mapper",
    "get_tts_service",
    "get_agent_service",
    "get_stm_service",
    "get_ltm_service",
    "get_emotion_motion_mapper",
]
