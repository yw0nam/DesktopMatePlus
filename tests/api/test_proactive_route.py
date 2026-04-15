"""Tests for POST /v1/proactive/trigger endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.proactive import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestProactiveTriggerEndpoint:
    def test_missing_session_id_returns_422(self, client):
        resp = client.post("/v1/proactive/trigger", json={"trigger_type": "webhook"})
        assert resp.status_code == 422

    @patch("src.api.routes.proactive.get_proactive_service")
    def test_service_not_available_returns_503(self, mock_get, client):
        mock_get.return_value = None
        resp = client.post(
            "/v1/proactive/trigger",
            json={"session_id": "test-session", "trigger_type": "webhook"},
        )
        assert resp.status_code == 503

    @patch("src.api.routes.proactive.get_proactive_service")
    def test_session_not_found_returns_404(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc._ws_manager.connections = {}
        mock_get.return_value = mock_svc
        resp = client.post(
            "/v1/proactive/trigger",
            json={"session_id": str(uuid4()), "trigger_type": "webhook"},
        )
        assert resp.status_code == 404

    @patch("src.api.routes.proactive.get_proactive_service")
    def test_invalid_session_id_format_returns_400(self, mock_get, client):
        mock_svc = MagicMock()
        mock_get.return_value = mock_svc
        resp = client.post(
            "/v1/proactive/trigger",
            json={"session_id": "not-a-uuid", "trigger_type": "webhook"},
        )
        assert resp.status_code == 400

    @patch("src.api.routes.proactive.get_proactive_service")
    def test_successful_trigger(self, mock_get, client):
        mock_svc = MagicMock()
        conn_id = uuid4()
        mock_conn = MagicMock()
        mock_svc._ws_manager.connections = {conn_id: mock_conn}
        mock_svc.trigger_proactive = AsyncMock(
            return_value={"status": "triggered", "turn_id": "t1"}
        )
        mock_get.return_value = mock_svc

        resp = client.post(
            "/v1/proactive/trigger",
            json={"session_id": str(conn_id), "trigger_type": "webhook"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "triggered"
