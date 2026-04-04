"""TTS API routes."""

from asyncio import to_thread

from fastapi import APIRouter, HTTPException, status

from src.models.tts import SpeakRequest, SpeakResponse, VoicesResponse
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


@router.post(
    "/speak",
    summary="Synthesize speech from text",
    response_model=SpeakResponse,
    status_code=status.HTTP_200_OK,
    responses={
        503: {"description": "TTS service not initialized or synthesis failed"},
        422: {"description": "Invalid request body"},
    },
)
async def speak(body: SpeakRequest) -> SpeakResponse:
    tts_service = get_tts_service()
    if tts_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service not available",
        )
    audio_base64 = await to_thread(
        tts_service.generate_speech,
        body.text,
        None,
        "base64",
        audio_format="wav",
    )
    if not isinstance(audio_base64, str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS synthesis failed",
        )
    return SpeakResponse(audio_base64=audio_base64)


__all__ = ["router"]
