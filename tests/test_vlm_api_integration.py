"""Tests for VLM API integration."""

from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_vlm_engine():
    """Create a mock VLM engine."""
    return Mock()


class TestVLMAPIIntegration:
    """Test VLM API endpoint integration."""

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_success(self, mock_vlm_service, client):
        """Test successful image analysis."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_response.return_value = (
            "A beautiful landscape with mountains and a lake"
        )
        mock_vlm_service.vlm_engine = mock_engine

        # Make request
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": "https://example.com/image.jpg",
                "prompt": "Describe this image",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "description" in data
        assert data["description"] == "A beautiful landscape with mountains and a lake"

        # Verify mock was called correctly
        mock_engine.generate_response.assert_called_once_with(
            image="https://example.com/image.jpg",
            prompt="Describe this image",
        )

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_with_base64(self, mock_vlm_service, client):
        """Test image analysis with base64-encoded image."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_response.return_value = "A cat sitting on a couch"
        mock_vlm_service.vlm_engine = mock_engine

        base64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Make request
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": base64_image,
                "prompt": "What do you see?",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["description"] == "A cat sitting on a couch"

        # Verify mock was called correctly
        mock_engine.generate_response.assert_called_once_with(
            image=base64_image,
            prompt="What do you see?",
        )

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_default_prompt(self, mock_vlm_service, client):
        """Test image analysis with default prompt."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_response.return_value = "An image description"
        mock_vlm_service.vlm_engine = mock_engine

        # Make request without prompt (should use default)
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": "https://example.com/test.jpg",
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK

        # Verify default prompt was used
        mock_engine.generate_response.assert_called_once_with(
            image="https://example.com/test.jpg",
            prompt="Describe this image",
        )

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_service_not_initialized(self, mock_vlm_service, client):
        """Test error when VLM service is not initialized."""
        # Setup mock with no engine
        mock_vlm_service.vlm_engine = None

        # Make request
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": "https://example.com/image.jpg",
                "prompt": "Describe this image",
            },
        )

        # Assert error response
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "detail" in data
        assert "VLM service not initialized" in data["detail"]

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_processing_error(self, mock_vlm_service, client):
        """Test error handling when VLM processing fails."""
        # Setup mock to raise exception
        mock_engine = Mock()
        mock_engine.generate_response.side_effect = Exception("VLM model error")
        mock_vlm_service.vlm_engine = mock_engine

        # Make request
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": "https://example.com/image.jpg",
                "prompt": "Describe this image",
            },
        )

        # Assert error response
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Error processing VLM request" in data["detail"]
        assert "VLM model error" in data["detail"]

    def test_analyze_image_missing_image(self, client):
        """Test validation error when image is missing."""
        # Make request without image
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "prompt": "Describe this image",
            },
        )

        # Assert validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_empty_response(self, mock_vlm_service, client):
        """Test handling of empty VLM response."""
        # Setup mock to return empty string
        mock_engine = Mock()
        mock_engine.generate_response.return_value = ""
        mock_vlm_service.vlm_engine = mock_engine

        # Make request
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": "https://example.com/image.jpg",
                "prompt": "Describe this image",
            },
        )

        # Assert successful response even with empty description
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["description"] == ""

    @patch("src.api.routes.vlm._vlm_service")
    def test_analyze_image_long_prompt(self, mock_vlm_service, client):
        """Test image analysis with a long prompt."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.generate_response.return_value = "Detailed analysis result"
        mock_vlm_service.vlm_engine = mock_engine

        long_prompt = (
            "Describe this image in detail, including colors, objects, composition, lighting, and any text visible. "
            * 5
        )

        # Make request
        response = client.post(
            "/v1/vlm/analyze",
            json={
                "image": "https://example.com/image.jpg",
                "prompt": long_prompt,
            },
        )

        # Assert response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["description"] == "Detailed analysis result"

        # Verify long prompt was passed correctly
        mock_engine.generate_response.assert_called_once_with(
            image="https://example.com/image.jpg",
            prompt=long_prompt,
        )
