"""Health check service for monitoring external dependencies."""

from typing import Tuple

import httpx

from src.configs.settings import settings
from src.models.responses import HealthResponse, ModuleStatus


class HealthService:
    """Service for checking the health of system modules."""

    def __init__(self, timeout: int = None):
        """Initialize health service.

        Args:
            timeout: Timeout for health checks in seconds. Uses settings default if not provided.
        """
        self.timeout = timeout or settings.health_check_timeout

    async def check_vlm(self) -> Tuple[bool, str | None]:
        """Check VLM (Vision Language Model) service health.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{settings.vlm_base_url}/health")
                if response.status_code == 200:
                    return True, None
                return False, f"VLM returned status code {response.status_code}"
        except httpx.TimeoutException:
            return False, "VLM service timeout"
        except httpx.ConnectError:
            return False, "VLM service unavailable"
        except Exception as e:
            return False, f"VLM check failed: {str(e)}"

    async def check_tts(self) -> Tuple[bool, str | None]:
        """Check TTS (Text-to-Speech) service health.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{settings.tts_base_url}/health")
                if response.status_code == 200:
                    return True, None
                return False, f"TTS returned status code {response.status_code}"
        except httpx.TimeoutException:
            return False, "TTS service timeout"
        except httpx.ConnectError:
            return False, "TTS service unavailable"
        except Exception as e:
            return False, f"TTS check failed: {str(e)}"

    async def check_agent(self) -> Tuple[bool, str | None]:
        """Check LangGraph agent health.

        Currently returns ready=True as agent is in-process.
        This will be updated when agent module is implemented.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            # TODO: Implement actual agent health check when agent module is ready
            # For now, just check if we can import the module
            # This is a placeholder that always returns True
            return True, None
        except Exception as e:
            return False, f"Agent check failed: {str(e)}"

    async def get_system_health(self) -> HealthResponse:
        """Get overall system health status.

        Checks all modules (VLM, TTS, Agent) and returns aggregated health status.

        Returns:
            HealthResponse model with overall status and individual module statuses
        """
        # Check all modules concurrently
        vlm_ready, vlm_error = await self.check_vlm()
        tts_ready, tts_error = await self.check_tts()
        agent_ready, agent_error = await self.check_agent()

        modules = [
            ModuleStatus(name="VLM", ready=vlm_ready, error=vlm_error),
            ModuleStatus(name="TTS", ready=tts_ready, error=tts_error),
            ModuleStatus(name="Agent", ready=agent_ready, error=agent_error),
        ]

        # Overall status is healthy only if all modules are ready
        all_ready = vlm_ready and tts_ready and agent_ready
        overall_status = "healthy" if all_ready else "unhealthy"

        return HealthResponse(status=overall_status, modules=modules)


# Create a singleton instance
health_service = HealthService()
