"""Tests for health check endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app
from src.models.responses import HealthResponse, ModuleStatus
from src.services.health import HealthService

client = TestClient(app)


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_all_services_healthy(self):
        """Test health check when all services are healthy."""
        # Mock the health service
        mock_health_response = HealthResponse(
            status="healthy",
            modules=[
                ModuleStatus(name="VLM", ready=True, error=None),
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
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
            assert len(data["modules"]) == 3
            assert all(module["ready"] for module in data["modules"])

    @pytest.mark.asyncio
    async def test_health_check_vlm_unhealthy(self):
        """Test health check when VLM service is unhealthy."""
        mock_health_response = HealthResponse(
            status="unhealthy",
            modules=[
                ModuleStatus(name="VLM", ready=False, error="VLM service unavailable"),
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
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
            vlm_module = next(m for m in data["modules"] if m["name"] == "VLM")
            assert vlm_module["ready"] is False
            assert vlm_module["error"] == "VLM service unavailable"

    @pytest.mark.asyncio
    async def test_health_check_tts_unhealthy(self):
        """Test health check when TTS service is unhealthy."""
        mock_health_response = HealthResponse(
            status="unhealthy",
            modules=[
                ModuleStatus(name="VLM", ready=True, error=None),
                ModuleStatus(name="TTS", ready=False, error="TTS service timeout"),
                ModuleStatus(name="Agent", ready=True, error=None),
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
            tts_module = next(m for m in data["modules"] if m["name"] == "TTS")
            assert tts_module["ready"] is False
            assert tts_module["error"] == "TTS service timeout"

    @pytest.mark.asyncio
    async def test_health_check_all_services_unhealthy(self):
        """Test health check when all services are unhealthy."""
        mock_health_response = HealthResponse(
            status="unhealthy",
            modules=[
                ModuleStatus(name="VLM", ready=False, error="VLM service unavailable"),
                ModuleStatus(name="TTS", ready=False, error="TTS service unavailable"),
                ModuleStatus(
                    name="Agent", ready=False, error="Agent initialization failed"
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
    async def test_health_check_response_structure(self):
        """Test that health check response has correct structure."""
        mock_health_response = HealthResponse(
            status="healthy",
            modules=[
                ModuleStatus(name="VLM", ready=True, error=None),
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
            ],
        )

        with patch(
            "src.api.routes.health_service.get_system_health",
            new_callable=AsyncMock,
            return_value=mock_health_response,
        ):
            response = client.get("/health")

            data = response.json()
            # Check required fields exist
            assert "status" in data
            assert "timestamp" in data
            assert "modules" in data

            # Check modules structure
            for module in data["modules"]:
                assert "name" in module
                assert "ready" in module
                assert "error" in module


class TestHealthService:
    """Test suite for HealthService."""

    @pytest.mark.asyncio
    async def test_check_vlm_success(self):
        """Test VLM health check with successful response."""
        service = HealthService(timeout=5)

        # Mock the VLM service container with a healthy engine
        with patch("src.services._vlm_service") as mock_vlm_service_container:
            mock_vlm_engine = MagicMock()
            mock_vlm_engine.health_check.return_value = True
            mock_vlm_service_container.vlm_engine = mock_vlm_engine

            ready, error = await service.check_vlm()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_vlm_connection_error(self):
        """Test VLM health check with connection error."""
        service = HealthService(timeout=5)

        # Mock the VLM service container with an unhealthy engine
        with patch("src.services._vlm_service") as mock_vlm_service_container:
            mock_vlm_engine = MagicMock()
            mock_vlm_engine.health_check.side_effect = Exception("Connection refused")
            mock_vlm_service_container.vlm_engine = mock_vlm_engine

            ready, error = await service.check_vlm()

            assert ready is False
            assert "VLM check failed" in error

    @pytest.mark.asyncio
    async def test_check_tts_success(self):
        """Test TTS health check with successful response."""
        service = HealthService(timeout=5)

        with patch("src.services._tts_service") as mock_tts_service_container:
            mock_tts_engine = MagicMock()
            mock_tts_engine.is_healthy.return_value = (True, "Service healthy")
            mock_tts_service_container.tts_engine = mock_tts_engine

            ready, error = await service.check_tts()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_agent_always_ready(self):
        """Test Agent health check (currently always returns ready)."""
        service = HealthService(timeout=5)

        ready, error = await service.check_agent()

        assert ready is True
        assert error is None

    @pytest.mark.asyncio
    async def test_get_system_health_all_healthy(self):
        """Test system health aggregation when all modules are healthy."""
        service = HealthService(timeout=5)

        with (
            patch.object(service, "check_vlm", return_value=(True, None)),
            patch.object(service, "check_tts", return_value=(True, None)),
            patch.object(service, "check_agent", return_value=(True, None)),
        ):
            health = await service.get_system_health()

            assert health.status == "healthy"
            assert len(health.modules) == 3
            assert all(module.ready for module in health.modules)

    @pytest.mark.asyncio
    async def test_get_system_health_partial_failure(self):
        """Test system health aggregation with partial failures."""
        service = HealthService(timeout=5)

        with (
            patch.object(service, "check_vlm", return_value=(False, "VLM unavailable")),
            patch.object(service, "check_tts", return_value=(True, None)),
            patch.object(service, "check_agent", return_value=(True, None)),
        ):
            health = await service.get_system_health()

            assert health.status == "unhealthy"
            assert len(health.modules) == 3

            vlm_module = next(m for m in health.modules if m.name == "VLM")
            assert vlm_module.ready is False
            assert vlm_module.error == "VLM unavailable"
