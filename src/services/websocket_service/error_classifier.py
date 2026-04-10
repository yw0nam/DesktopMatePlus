"""Error classification for WebSocket operations.

Backward-compatible re-export of src.core.error_classifier, extended with
WebSocket-specific exception mappings (WebSocketDisconnect, ValidationError).
"""

from fastapi import WebSocketDisconnect
from pydantic import ValidationError

from src.core.error_classifier import ErrorClassifier as _BaseClassifier
from src.core.error_classifier import ErrorSeverity

# Re-export for existing imports
__all__ = ["ErrorClassifier", "ErrorSeverity"]


class ErrorClassifier(_BaseClassifier):
    """WebSocket-aware ErrorClassifier with additional exception mappings."""

    SEVERITY_MAP = {
        **_BaseClassifier.SEVERITY_MAP,
        # WebSocket-specific: client disconnect is fatal
        WebSocketDisconnect: ErrorSeverity.FATAL,
        # Pydantic validation failures are recoverable (bad client input)
        ValidationError: ErrorSeverity.RECOVERABLE,
    }
