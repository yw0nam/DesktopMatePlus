"""API route modules."""

from fastapi import APIRouter

# Create main router
router = APIRouter()


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


__all__ = ["router"]
