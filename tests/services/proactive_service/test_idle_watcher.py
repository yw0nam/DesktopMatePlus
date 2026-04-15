"""Tests for idle watcher and ConnectionState timestamp."""

import time
from unittest.mock import MagicMock
from uuid import uuid4

from src.services.websocket_service.manager.connection import ConnectionState


class TestConnectionStateTimestamp:
    def test_last_user_message_at_initialized_to_created_at(self):
        ws = MagicMock()
        conn = ConnectionState(ws, uuid4())
        assert conn.last_user_message_at == conn.created_at

    def test_last_user_message_at_is_updatable(self):
        ws = MagicMock()
        conn = ConnectionState(ws, uuid4())
        now = time.time()
        conn.last_user_message_at = now
        assert conn.last_user_message_at == now
