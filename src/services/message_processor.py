"""MessageProcessor Core Orchestrator - Compatibility Import.

This module provides backward compatibility by importing the MessageProcessor
from the new websocket_service module.
"""

from src.services.websocket_service.message_processor import MessageProcessor

__all__ = ["MessageProcessor"]
