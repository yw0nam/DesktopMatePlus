"""Tests for health check endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from src.models.responses import HealthResponse, ModuleStatus
from src.services.health import HealthService


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_all_services_healthy(self, client):
        """Test health check when all services are healthy."""
        mock_health_response = HealthResponse(
            status="healthy",
            modules=[
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
                ModuleStatus(name="LTM", ready=True, error=None),
                ModuleStatus(name="MongoDB", ready=True, error=None),
            ],
        )

        with patch(
            "src.api.routes.health_service.get_system_health",
            new_callable=AsyncMock,
            return_value=mock_health_response,
        ):
            response = client.get("/health")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert len(data["modules"]) == 4
            assert all(module["ready"] for module in data["modules"])

    @pytest.mark.asyncio
    async def test_health_check_all_services_unhealthy(self, client):
        """Test health check when all services are unhealthy."""
        mock_health_response = HealthResponse(
            status="unhealthy",
            modules=[
                ModuleStatus(name="TTS", ready=False, error="TTS service unavailable"),
                ModuleStatus(
                    name="Agent", ready=False, error="Agent initialization failed"
                ),
                ModuleStatus(name="LTM", ready=False, error="LTM service unavailable"),
                ModuleStatus(
                    name="MongoDB", ready=False, error="MongoDB service unavailable"
                ),
            ],
        )

        with patch(
            "src.api.routes.health_service.get_system_health",
            new_callable=AsyncMock,
            return_value=mock_health_response,
        ):
            response = client.get("/health")

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
            assert all(not module["ready"] for module in data["modules"])
            assert all(module["error"] is not None for module in data["modules"])

    @pytest.mark.asyncio
    async def test_health_check_response_structure(self, client):
        """Test that health check response has correct structure."""
        mock_health_response = HealthResponse(
            status="healthy",
            modules=[
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
                ModuleStatus(name="LTM", ready=True, error=None),
                ModuleStatus(name="MongoDB", ready=True, error=None),
            ],
        )

        with patch(
            "src.api.routes.health_service.get_system_health",
            new_callable=AsyncMock,
            return_value=mock_health_response,
        ):
            response = client.get("/health")

            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            assert "modules" in data

            for module in data["modules"]:
                assert "name" in module
                assert "ready" in module
                assert "error" in module


class TestHealthService:
    """Test suite for HealthService."""

    @pytest.mark.asyncio
    async def test_check_tts_success(self):
        """Test TTS health check with successful response."""
        service = HealthService(timeout=5)

        with patch("src.services.get_tts_service") as mock_get_tts:
            mock_tts_engine = MagicMock()
            mock_tts_engine.is_healthy.return_value = (True, "Service healthy")
            mock_get_tts.return_value = mock_tts_engine

            ready, error = await service.check_tts()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_agent_success(self):
        """Test Agent health check with successful response."""
        service = HealthService(timeout=5)

        with patch("src.services.get_agent_service") as mock_get_agent:
            mock_agent_engine = MagicMock()
            mock_agent_engine.is_healthy.return_value = (True, "Agent is healthy")
            mock_get_agent.return_value = mock_agent_engine

            ready, error = await service.check_agent()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_ltm_success(self):
        """Test LTM health check with successful response."""
        service = HealthService(timeout=5)

        with patch("src.services.get_ltm_service") as mock_get_ltm:
            mock_ltm_engine = MagicMock()
            mock_ltm_engine.is_healthy.return_value = (True, "LTM is healthy")
            mock_get_ltm.return_value = mock_ltm_engine

            ready, error = await service.check_ltm()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_mongodb_success(self):
        """Test MongoDB health check with successful response."""
        service = HealthService(timeout=5)

        with patch("src.services.service_manager.get_mongo_client") as mock_get_mongo:
            mock_client = MagicMock()
            mock_client.admin.command.return_value = {"ok": 1}
            mock_get_mongo.return_value = mock_client

            ready, error = await service.check_mongodb()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_get_system_health_all_healthy(self):
        """Test system health aggregation when all modules are healthy."""
        service = HealthService(timeout=5)

        with (
            patch.object(service, "check_tts", return_value=(True, None)),
            patch.object(service, "check_agent", return_value=(True, None)),
            patch.object(service, "check_ltm", return_value=(True, None)),
            patch.object(service, "check_mongodb", return_value=(True, None)),
        ):
            health = await service.get_system_health()

            assert health.status == "healthy"
            assert len(health.modules) == 4
            assert all(module.ready for module in health.modules)

    @pytest.mark.asyncio
    async def test_get_system_health_partial_failure(self):
        """Test system health aggregation with partial failures."""
        service = HealthService(timeout=5)

        with (
            patch.object(service, "check_tts", return_value=(True, None)),
            patch.object(service, "check_agent", return_value=(True, None)),
            patch.object(
                service, "check_ltm", return_value=(False, "LTM service unavailable")
            ),
            patch.object(
                service,
                "check_mongodb",
                return_value=(False, "MongoDB service unavailable"),
            ),
        ):
            health = await service.get_system_health()

            assert health.status == "unhealthy"
            assert len(health.modules) == 4

            ltm_module = next(m for m in health.modules if m.name == "LTM")
            assert ltm_module.ready is False
            assert ltm_module.error == "LTM service unavailable"

            mongodb_module = next(m for m in health.modules if m.name == "MongoDB")
            assert mongodb_module.ready is False
            assert mongodb_module.error == "MongoDB service unavailable"
