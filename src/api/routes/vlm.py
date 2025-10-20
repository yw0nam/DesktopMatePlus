"""VLM API routes."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services import get_vlm_service

router = APIRouter(prefix="/v1/vlm", tags=["VLM"])


class VLMRequest(BaseModel):
    """Request model for VLM vision analysis."""

    image: str = Field(
        ...,
        description="Image data as base64-encoded string or URL",
    )
    prompt: str = Field(
        default="Describe this image",
        description="Text prompt for image analysis",
    )


class VLMResponse(BaseModel):
    """Response model for VLM vision analysis."""

    description: str = Field(
        ...,
        description="Textual description of the image",
    )


@router.post(
    "/analyze",
    response_model=VLMResponse,
    summary="Analyze image with VLM",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Image analyzed successfully",
            "model": VLMResponse,
        },
        500: {
            "description": "VLM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error processing VLM request: ..."}
                }
            },
        },
        503: {
            "description": "VLM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "VLM service not initialized"}
                }
            },
        },
    },
)
async def analyze_image(request: VLMRequest) -> VLMResponse:
    """Analyze an image using the VLM service.

    This endpoint accepts an image (as base64-encoded string or URL) and a
    prompt, sends it to the vLLM server, and returns a textual description.

    Args:
        request: VLM request containing image and prompt

    Returns:
        VLMResponse: Textual description of the image

    Raises:
        HTTPException: If VLM service is not initialized or processing fails
    """
    vlm_service = get_vlm_service()

    if vlm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VLM service not initialized",
        )

    try:
        # Call VLM service to generate description
        description = vlm_service.generate_response(
            image=request.image,
            prompt=request.prompt,
        )

        return VLMResponse(description=description)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing VLM request: {str(e)}",
        ) from e


__all__ = ["router"]
