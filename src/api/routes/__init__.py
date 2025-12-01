"""API route modules."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from src.api.routes import ltm, stm, tts, vlm, websocket
from src.models.responses import HealthResponse
from src.services.health import HealthService, health_service

# Create main router
router = APIRouter()

# Include service routes
router.include_router(tts.router)
router.include_router(vlm.router)
router.include_router(websocket.router)
router.include_router(stm.router)
router.include_router(ltm.router)


def get_health_service() -> HealthService:
    """Dependency to get health service instance.

    Returns:
        HealthService: The health service singleton
    """
    return health_service


@router.get("/", summary="Root endpoint", tags=["Root"])
async def read_root():
    """Root endpoint that returns a welcome message.

    Returns:
        dict: A welcome message indicating the API is running.
    """
    return {
        "message": "DesktopMate+ Backend API is running",
        "version": "0.1.0",
        "docs": "/docs",
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    tags=["Health"],
    responses={
        200: {
            "description": "All services are healthy",
            "model": HealthResponse,
        },
        503: {
            "description": "One or more services are unhealthy",
            "model": HealthResponse,
        },
    },
)
async def health_check(
    service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """Check the health of all system modules.

    Returns health status for:
    - VLM (Vision Language Model) service
    - TTS (Text-to-Speech) service
    - Agent (LangGraph) module

    Returns:
        JSONResponse: Health status with appropriate HTTP status code
            - 200 if all modules are healthy
            - 503 if any module is unhealthy
    """
    health = await service.get_system_health()

    # Return 503 if any module is unhealthy
    status_code = (
        status.HTTP_200_OK
        if health.status == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=status_code,
        content=health.model_dump(mode="json"),
    )


__all__ = ["router"]
