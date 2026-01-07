"""TTS API routes."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from src.models.tts import TTSRequest, TTSResponse
from src.services import get_tts_service

router = APIRouter(prefix="/v1/tts", tags=["TTS"])


@router.post(
    "/synthesize",
    summary="Synthesize speech from text",
    status_code=status.HTTP_200_OK,
    response_model=None,
    responses={
        200: {
            "description": "Speech synthesized successfully",
            "content": {
                "application/json": {},
                "audio/wav": {"schema": {"type": "string", "format": "binary"}},
                "audio/mpeg": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        400: {
            "description": "Invalid input or empty text",
            "content": {
                "application/json": {"example": {"detail": "Text cannot be empty"}}
            },
        },
        500: {
            "description": "TTS service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error processing TTS request: ..."}
                }
            },
        },
        503: {
            "description": "TTS service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "TTS service not initialized"}
                }
            },
        },
    },
)
async def synthesize_speech(request: TTSRequest) -> TTSResponse | Response:
    """Synthesize speech from text using the TTS service.

    This endpoint accepts text and optional voice reference, sends it to the
    TTS server, and returns audio data in the requested format.

    Args:
        request: TTS request containing text, optional reference_id, and output format

    Returns:
        TTSResponse: Audio data in the requested format

    Raises:
        HTTPException: If TTS service is not initialized, input is invalid, or processing fails
    """
    tts_service = get_tts_service()

    if tts_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service not initialized",
        )

    # Validate text is not empty
    if not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty",
        )

    try:
        # Call TTS service to generate speech
        audio_data = tts_service.generate_speech(
            text=request.text,
            reference_id=request.reference_id,
            output_format=request.output_format,
            audio_format=request.audio_format,
        )

        if audio_data is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="TTS service returned no audio data",
            )

        # Return binary response for bytes format
        if request.output_format == "bytes" and isinstance(audio_data, bytes):
            media_type = "audio/mpeg" if request.audio_format == "mp3" else "audio/wav"
            return Response(content=audio_data, media_type=media_type)

        # Return JSON response for base64 format
        audio_str = str(audio_data)
        return TTSResponse(
            audio_data=audio_str,
            format=request.output_format,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing TTS request: {str(e)}",
        ) from e


__all__ = ["router"]
