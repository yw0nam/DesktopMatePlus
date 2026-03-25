"""External service clients."""

from src.services.health import HealthService, health_service
from src.services.service_manager import (
    get_agent_service,
    get_emotion_motion_mapper,
    get_ltm_service,
    get_mongo_client,
    get_session_registry,
    get_tts_service,
    initialize_agent_service,
    initialize_emotion_motion_mapper,
    initialize_ltm_service,
    initialize_mongodb_client,
    initialize_services,
    initialize_tts_service,
)

__all__ = [
    "HealthService",
    "health_service",
    "initialize_services",
    "initialize_tts_service",
    "initialize_agent_service",
    "initialize_ltm_service",
    "initialize_emotion_motion_mapper",
    "initialize_mongodb_client",
    "get_tts_service",
    "get_agent_service",
    "get_ltm_service",
    "get_emotion_motion_mapper",
    "get_mongo_client",
    "get_session_registry",
]
