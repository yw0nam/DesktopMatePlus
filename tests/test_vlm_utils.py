"""
Tests for VLM service utilities (Base64 encoding, image preparation).
"""

import base64
import io

import pytest
from PIL import Image

from src.services.vlm_service.utils import (
    create_base64_image_dict,
    create_url_image_dict,
    encode_image_to_base64,
    prepare_image_for_vlm,
)


def create_test_image() -> bytes:
    """Create a simple test image as bytes."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes.getvalue()


class TestEncodeImageToBase64:
    """Tests for encode_image_to_base64 function."""

    def test_encode_valid_image(self):
        """Test encoding valid image bytes to base64."""
        image_bytes = create_test_image()
        result = encode_image_to_base64(image_bytes)

        # Verify it's a valid base64 string
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify it can be decoded back
        decoded = base64.b64decode(result)
        assert decoded == image_bytes

    def test_encode_empty_bytes(self):
        """Test that empty bytes raise ValueError."""
        with pytest.raises(ValueError, match="Image bytes cannot be empty"):
            encode_image_to_base64(b"")

    def test_encode_none(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="Image bytes cannot be empty"):
            encode_image_to_base64(None)


class TestCreateBase64ImageDict:
    """Tests for create_base64_image_dict function."""

    def test_create_dict_default_mime(self):
        """Test creating dict with default MIME type."""
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
        result = create_base64_image_dict(base64_data)

        assert result["type"] == "image"
        assert result["source_type"] == "base64"
        assert result["data"] == base64_data
        assert result["mime_type"] == "image/png"

    def test_create_dict_custom_mime(self):
        """Test creating dict with custom MIME type."""
        base64_data = "test_data"
        result = create_base64_image_dict(base64_data, mime_type="image/jpeg")

        assert result["mime_type"] == "image/jpeg"


class TestCreateUrlImageDict:
    """Tests for create_url_image_dict function."""

    def test_create_dict_http_url(self):
        """Test creating dict with HTTP URL."""
        url = "https://example.com/image.png"
        result = create_url_image_dict(url)

        assert result["type"] == "image"
        assert result["source_type"] == "url"
        assert result["url"] == url

    def test_create_dict_data_uri(self):
        """Test creating dict with data URI."""
        url = "data:image/png;base64,iVBORw0..."
        result = create_url_image_dict(url)

        assert result["url"] == url


class TestPrepareImageForVLM:
    """Tests for prepare_image_for_vlm function."""

    def test_prepare_url_string(self):
        """Test preparing URL string for VLM."""
        url = "https://example.com/test.png"
        result = prepare_image_for_vlm(url)

        assert result["type"] == "image"
        assert result["source_type"] == "url"
        assert result["url"] == url

    def test_prepare_bytes_default_mime(self):
        """Test preparing bytes with default MIME type."""
        image_bytes = create_test_image()
        result = prepare_image_for_vlm(image_bytes)

        assert result["type"] == "image"
        assert result["source_type"] == "base64"
        assert "data" in result
        assert result["mime_type"] == "image/png"

        # Verify the base64 data can be decoded
        decoded = base64.b64decode(result["data"])
        assert decoded == image_bytes

    def test_prepare_bytes_custom_mime(self):
        """Test preparing bytes with custom MIME type."""
        image_bytes = create_test_image()
        result = prepare_image_for_vlm(image_bytes, mime_type="image/jpeg")

        assert result["mime_type"] == "image/jpeg"

    def test_prepare_invalid_type(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid image type"):
            prepare_image_for_vlm(123)

        with pytest.raises(ValueError, match="Invalid image type"):
            prepare_image_for_vlm([1, 2, 3])


class TestIntegrationWithScreenCapture:
    """Integration tests with screen capture service."""

    def test_screen_capture_bytes_to_vlm_format(self):
        """Test converting screen capture bytes to VLM format."""
        # Simulate screen capture output
        image_bytes = create_test_image()

        # Prepare for VLM
        vlm_input = prepare_image_for_vlm(image_bytes)

        # Verify structure
        assert vlm_input["type"] == "image"
        assert vlm_input["source_type"] == "base64"
        assert len(vlm_input["data"]) > 0
        assert vlm_input["mime_type"] == "image/png"

    def test_base64_string_can_be_decoded(self):
        """Test that base64 string from utils can be properly decoded."""
        original_bytes = create_test_image()
        base64_str = encode_image_to_base64(original_bytes)

        # Decode and verify
        decoded_bytes = base64.b64decode(base64_str)
        assert decoded_bytes == original_bytes

        # Verify it's a valid image
        img = Image.open(io.BytesIO(decoded_bytes))
        assert img.size == (100, 100)
