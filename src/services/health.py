"""Health check service for monitoring external dependencies."""

from typing import Tuple

from src.models.responses import HealthResponse, ModuleStatus


class HealthService:
    """Service for checking the health of system modules."""

    def __init__(self, timeout: int = None):
        """Initialize health service.

        Args:
            timeout: Timeout for health checks in seconds. Uses settings default if not provided.
        """
        if timeout is None:
            # Lazy load settings to avoid circular import and module-level initialization issues
            try:
                from src.configs.settings import get_settings

                settings = get_settings()
                self.timeout = settings.health_check_timeout
            except RuntimeError:
                # Settings not initialized yet (e.g., during tests), use default
                self.timeout = 5
        else:
            self.timeout = timeout

    async def check_vlm(self) -> Tuple[bool, str | None]:
        """Check VLM (Vision Language Model) service health.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            from src.services import get_vlm_service

            # Get VLM engine and check health
            vlm_engine = get_vlm_service()
            if vlm_engine is None:
                return False, "VLM service not initialized"

            is_healthy, message = vlm_engine.is_healthy()

            if is_healthy:
                return True, None
            else:
                return False, str(message) if message else "VLM service unhealthy"

        except Exception as e:
            return False, f"VLM check failed: {str(e)}"

    async def check_tts(self) -> Tuple[bool, str | None]:
        """Check TTS (Text-to-Speech) service health.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            from src.services import get_tts_service

            # Get TTS engine and check health
            tts_engine = get_tts_service()
            if tts_engine is None:
                return False, "TTS service not initialized"

            is_healthy, message = tts_engine.is_healthy()

            if is_healthy:
                return True, None
            else:
                return False, str(message) if message else "TTS service unhealthy"

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

    async def check_ltm(self) -> Tuple[bool, str | None]:
        """Check Long-Term Memory (LTM) service health.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            from src.services import get_ltm_service

            # Get LTM engine and check health
            ltm_engine = get_ltm_service()
            if ltm_engine is None:
                return False, "LTM service not initialized"

            is_healthy, message = ltm_engine.is_healthy()

            if is_healthy:
                return True, None
            else:
                return False, str(message) if message else "LTM service unhealthy"

        except Exception as e:
            return False, f"LTM check failed: {str(e)}"

    async def check_stm(self) -> Tuple[bool, str | None]:
        """Check Short-Term Memory (STM) service health.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            from src.services import get_stm_service

            # Get STM engine and check health
            stm_engine = get_stm_service()
            if stm_engine is None:
                return False, "STM service not initialized"

            is_healthy, message = stm_engine.is_healthy()

            if is_healthy:
                return True, None
            else:
                return False, str(message) if message else "STM service unhealthy"

        except Exception as e:
            return False, f"STM check failed: {str(e)}"

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
        ltm_ready, ltm_error = await self.check_ltm()
        stm_ready, stm_error = await self.check_stm()

        modules = [
            ModuleStatus(name="VLM", ready=vlm_ready, error=vlm_error),
            ModuleStatus(name="TTS", ready=tts_ready, error=tts_error),
            ModuleStatus(name="Agent", ready=agent_ready, error=agent_error),
            ModuleStatus(name="LTM", ready=ltm_ready, error=ltm_error),
            ModuleStatus(name="STM", ready=stm_ready, error=stm_error),
        ]

        # Overall status is healthy only if all modules are ready
        all_ready = vlm_ready and tts_ready and agent_ready and ltm_ready and stm_ready
        overall_status = "healthy" if all_ready else "unhealthy"

        return HealthResponse(status=overall_status, modules=modules)


# Create a singleton instance
health_service = HealthService()
