"""TTS API routes."""

from fastapi import APIRouter, HTTPException, status

from src.models.tts import VoicesResponse
from src.services import get_tts_service

router = APIRouter(prefix="/v1/tts", tags=["TTS"])


@router.get(
    "/voices",
    summary="List available TTS reference voices",
    response_model=VoicesResponse,
    status_code=status.HTTP_200_OK,
    responses={
        503: {"description": "TTS service not initialized"},
    },
)
async def list_voices() -> VoicesResponse:
    tts_service = get_tts_service()
    if tts_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service not available",
        )
    return VoicesResponse(voices=tts_service.list_voices())


__all__ = ["router"]
