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
        # Mock the health service
        mock_health_response = HealthResponse(
            status="healthy",
            modules=[
                ModuleStatus(name="VLM", ready=True, error=None),
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
                ModuleStatus(name="LTM", ready=True, error=None),
                ModuleStatus(name="STM", ready=True, error=None),
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
            assert len(data["modules"]) == 5
            assert all(module["ready"] for module in data["modules"])

    @pytest.mark.asyncio
    async def test_health_check_all_services_unhealthy(self, client):
        """Test health check when all services are unhealthy."""
        mock_health_response = HealthResponse(
            status="unhealthy",
            modules=[
                ModuleStatus(name="VLM", ready=False, error="VLM service unavailable"),
                ModuleStatus(name="TTS", ready=False, error="TTS service unavailable"),
                ModuleStatus(
                    name="Agent", ready=False, error="Agent initialization failed"
                ),
                ModuleStatus(name="LTM", ready=False, error="LTM service unavailable"),
                ModuleStatus(name="STM", ready=False, error="STM service unavailable"),
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
                ModuleStatus(name="VLM", ready=True, error=None),
                ModuleStatus(name="TTS", ready=True, error=None),
                ModuleStatus(name="Agent", ready=True, error=None),
                ModuleStatus(name="LTM", ready=True, error=None),
                ModuleStatus(name="STM", ready=True, error=None),
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

        # Mock the VLM service getter to return a healthy engine
        with patch("src.services.get_vlm_service") as mock_get_vlm:
            mock_vlm_engine = MagicMock()
            mock_vlm_engine.is_healthy.return_value = (True, "VLM service is healthy")
            mock_get_vlm.return_value = mock_vlm_engine

            ready, error = await service.check_vlm()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_tts_success(self):
        """Test TTS health check with successful response."""
        service = HealthService(timeout=5)

        # Mock the TTS service getter to return a healthy engine
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

        # Mock the Agent service getter to return a healthy engine
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

        # Mock the LTM service getter to return a healthy engine
        with patch("src.services.get_ltm_service") as mock_get_ltm:
            mock_ltm_engine = MagicMock()
            mock_ltm_engine.is_healthy.return_value = (True, "LTM is healthy")
            mock_get_ltm.return_value = mock_ltm_engine

            ready, error = await service.check_ltm()

            assert ready is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_stm_success(self):
        """Test STM health check with successful response."""
        service = HealthService(timeout=5)

        # Mock the STM service getter to return a healthy engine
        with patch("src.services.get_stm_service") as mock_get_stm:
            mock_stm_engine = MagicMock()
            mock_stm_engine.is_healthy.return_value = (True, "STM is healthy")
            mock_get_stm.return_value = mock_stm_engine

            ready, error = await service.check_stm()

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
            patch.object(service, "check_ltm", return_value=(True, None)),
            patch.object(service, "check_stm", return_value=(True, None)),
        ):
            health = await service.get_system_health()

            assert health.status == "healthy"
            assert len(health.modules) == 5
            assert all(module.ready for module in health.modules)

    @pytest.mark.asyncio
    async def test_get_system_health_partial_failure(self):
        """Test system health aggregation with partial failures."""
        service = HealthService(timeout=5)

        with (
            patch.object(service, "check_vlm", return_value=(False, "VLM unavailable")),
            patch.object(service, "check_tts", return_value=(True, None)),
            patch.object(service, "check_agent", return_value=(True, None)),
            patch.object(
                service, "check_ltm", return_value=(False, "LTM service unavailable")
            ),
            patch.object(
                service, "check_stm", return_value=(False, "STM service unavailable")
            ),
        ):
            health = await service.get_system_health()

            assert health.status == "unhealthy"
            assert len(health.modules) == 5

            vlm_module = next(m for m in health.modules if m.name == "VLM")
            assert vlm_module.ready is False
            assert vlm_module.error == "VLM unavailable"

            ltm_module = next(m for m in health.modules if m.name == "LTM")
            assert ltm_module.ready is False
            assert ltm_module.error == "LTM service unavailable"

            stm_module = next(m for m in health.modules if m.name == "STM")
            assert stm_module.ready is False
            assert stm_module.error == "STM service unavailable"
