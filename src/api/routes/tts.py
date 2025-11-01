"""TTS API routes."""

from fastapi import APIRouter, HTTPException, status

from src.models.tts import TTSRequest, TTSResponse
from src.services import get_tts_service

router = APIRouter(prefix="/v1/tts", tags=["TTS"])


@router.post(
    "/synthesize",
    response_model=TTSResponse,
    summary="Synthesize speech from text",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Speech synthesized successfully",
            "model": TTSResponse,
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
async def synthesize_speech(request: TTSRequest) -> TTSResponse:
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
        )

        if audio_data is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="TTS service returned no audio data",
            )

        # Convert bytes to string representation if needed
        if request.output_format == "bytes" and isinstance(audio_data, bytes):
            # For bytes format, we still encode to base64 for JSON transport
            import base64

            audio_str = base64.b64encode(audio_data).decode("utf-8")
        else:
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
