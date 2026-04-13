"""Health check service for monitoring external dependencies."""

from src.core.error_classifier import ErrorSeverity
from src.models.responses import HealthResponse, ModuleStatus


def classify_health_severity(error: str | None) -> ErrorSeverity | None:
    """Classify an error string into an ErrorSeverity level.

    Args:
        error: Error message string, or None if no error.

    Returns:
        ErrorSeverity level, or None if error is None.
    """
    if error is None:
        return None
    lower = error.lower()
    if any(
        kw in lower
        for kw in ("timeout", "timed out", "connection reset", "broken pipe")
    ):
        return ErrorSeverity.TRANSIENT
    if any(
        kw in lower
        for kw in ("not initialized", "invalid", "validation", "value error")
    ):
        return ErrorSeverity.RECOVERABLE
    return ErrorSeverity.FATAL


class HealthService:
    """Service for checking the health of system modules."""

    def __init__(self, timeout: int | None = None):
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

    async def check_tts(self) -> tuple[bool, str | None]:
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
            return False, f"TTS check failed: {e!s}"

    async def check_agent(self) -> tuple[bool, str | None]:
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
            return False, f"Agent check failed: {e!s}"

    async def check_ltm(self) -> tuple[bool, str | None]:
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
            return False, f"LTM check failed: {e!s}"

    async def check_mongodb(self) -> tuple[bool, str | None]:
        """Check MongoDB checkpointer connectivity.

        Returns:
            Tuple of (is_ready, error_message)
        """
        try:
            from src.services.service_manager import get_mongo_client

            client = get_mongo_client()
            if client is None:
                return False, "MongoDB client not initialized"

            client.admin.command("ping")
            return True, None

        except Exception as e:
            return False, f"MongoDB ping failed: {e!s}"

    async def get_system_health(self) -> HealthResponse:
        """Get overall system health status.

        Checks all modules (VLM, TTS, Agent) and returns aggregated health status.

        Returns:
            HealthResponse model with overall status and individual module statuses
        """
        # Check all modules concurrently
        tts_ready, tts_error = await self.check_tts()
        agent_ready, agent_error = await self.check_agent()
        ltm_ready, ltm_error = await self.check_ltm()
        mongodb_ready, mongodb_error = await self.check_mongodb()

        modules = [
            ModuleStatus(
                name="TTS",
                ready=tts_ready,
                error=tts_error,
                severity=classify_health_severity(tts_error),
            ),
            ModuleStatus(
                name="Agent",
                ready=agent_ready,
                error=agent_error,
                severity=classify_health_severity(agent_error),
            ),
            ModuleStatus(
                name="LTM",
                ready=ltm_ready,
                error=ltm_error,
                severity=classify_health_severity(ltm_error),
            ),
            ModuleStatus(
                name="MongoDB",
                ready=mongodb_ready,
                error=mongodb_error,
                severity=classify_health_severity(mongodb_error),
            ),
        ]

        # Overall status is healthy only if all modules are ready
        all_ready = tts_ready and agent_ready and ltm_ready and mongodb_ready
        overall_status = "healthy" if all_ready else "unhealthy"

        return HealthResponse(status=overall_status, modules=modules)


# Create a singleton instance
health_service = HealthService()
