"""Screen capture service for cross-platform screen capturing."""

from .screen_capture import (
    ScreenCaptureError,
    ScreenCaptureService,
    get_screen_capture_service,
)

__all__ = [
    "ScreenCaptureService",
    "ScreenCaptureError",
    "get_screen_capture_service",
]
