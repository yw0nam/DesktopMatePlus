"""
Utility functions for VLM service.

This module provides helper functions for image encoding and formatting
compatible with VLM API requirements (vLLM, OpenAI Vision API, etc.).
"""

import base64
from typing import Dict, Union


def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encode image bytes to Base64 string.

    Args:
        image_bytes: Raw image data as bytes (PNG, JPEG, etc.)

    Returns:
        str: Base64 encoded string (without data URI prefix)

    Raises:
        ValueError: If image_bytes is empty or invalid
    """
    if not image_bytes:
        raise ValueError("Image bytes cannot be empty")

    try:
        base64_str = base64.b64encode(image_bytes).decode("utf-8")
        return base64_str
    except Exception as e:
        raise ValueError(f"Failed to encode image to base64: {e}") from e


def create_base64_image_dict(
    base64_data: str, mime_type: str = "image/png"
) -> Dict[str, str]:
    """
    Create image dictionary for VLM API with base64 data.

    Args:
        base64_data: Base64 encoded image string
        mime_type: MIME type of the image (default: image/png)

    Returns:
        Dict containing type and image_url with data URI in OpenAI format
    """
    data_uri = f"data:{mime_type};base64,{base64_data}"
    return {"type": "image_url", "image_url": {"url": data_uri}}


def create_url_image_dict(url: str) -> Dict[str, str]:
    """
    Create image dictionary for VLM API with URL.

    Args:
        url: Image URL (can be http/https URL or data URI)

    Returns:
        Dict containing type and image_url in OpenAI format
    """
    return {"type": "image_url", "image_url": {"url": url}}


def prepare_image_for_vlm(
    images: Union[str, bytes, list[Union[str, bytes]]], mime_type: str = "image/png"
) -> Union[Dict[str, str], list[Dict[str, str]]]:
    """
    Prepare image input for VLM API request.

    Handles both URL strings and raw bytes, converting to appropriate format.
    Can accept single image or list of images.

    Args:
        images: Single image or list of images as URL string(s) or raw bytes
        mime_type: MIME type for bytes input (default: image/png)

    Returns:
        Dict or list of dicts with image data formatted for VLM API

    Raises:
        ValueError: If image type is not supported
    """
    # Handle single image (not a list)
    if isinstance(images, (str, bytes)):
        if isinstance(images, str):
            return create_url_image_dict(images)
        else:
            base64_str = encode_image_to_base64(images)
            return create_base64_image_dict(base64_str, mime_type)

    # Validate that it's a list before attempting iteration
    if not isinstance(images, list):
        raise ValueError(
            f"Invalid image type: {type(images)}. Expected str (URL), bytes, or list."
        )

    # Handle list of images
    image_dicts = []
    for image in images:
        if isinstance(image, str):
            image_dicts.append(create_url_image_dict(image))
        elif isinstance(image, bytes):
            base64_str = encode_image_to_base64(image)
            image_dicts.append(create_base64_image_dict(base64_str, mime_type))
        else:
            raise ValueError(
                f"Invalid image type in list: {type(image)}. Expected str (URL) or bytes."
            )
    return image_dicts
