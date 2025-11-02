"""
Tests for VLM service functionality.

Tests the VLM service integration with new factory pattern.
"""

import os
from unittest.mock import Mock, patch

import pytest

from src.services.vlm_service.openai_compatible import OpenAIService
from src.services.vlm_service.service import VLMService
from src.services.vlm_service.vlm_factory import VLMFactory


class TestVLMFactory:
    """Test VLM factory functionality."""

    def test_get_openai_service(self):
        """Test creating OpenAI VLM service via factory."""
        vlm_service = VLMFactory.get_vlm_service(
            "openai_chat_agent",
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )
        assert isinstance(vlm_service, OpenAIService)
        assert isinstance(vlm_service, VLMService)

    def test_get_unknown_service_type(self):
        """Test factory raises error for unknown service type."""
        with pytest.raises(ValueError, match="Unknown VLM service type"):
            VLMFactory.get_vlm_service("unknown_service")

    def test_factory_with_all_params(self):
        """Test factory with all parameters specified."""
        with patch.dict(os.environ, {"VLM_API_KEY": "key123"}):
            service = VLMFactory.get_vlm_service(
                service_type="openai_chat_agent",
                openai_api_key="key123",
                openai_api_base="https://custom.api/v1",
                model_name="gpt-4-vision",
            )

            assert isinstance(service, VLMService)
            assert service.openai_api_key == "key123"
            assert service.openai_api_base == "https://custom.api/v1"
            assert service.model_name == "gpt-4-vision"


class TestOpenAIService:
    """Test OpenAI VLM service functionality."""

    @patch("src.services.vlm_service.openai_compatible.ChatOpenAI")
    def test_initialize_model(self, mock_chat_openai):
        """Test model initialization."""
        mock_model = Mock()
        mock_chat_openai.return_value = mock_model

        service = OpenAIService(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )

        assert service.model == mock_model
        mock_chat_openai.assert_called_once_with(
            temperature=0.7,
            top_p=0.9,
            api_key="test_key",
            model_name="test_model",
            base_url="http://localhost:8001/v1",
        )

    @patch("src.services.vlm_service.openai_compatible.ChatOpenAI")
    def test_health_check_success(self, mock_chat_openai):
        """Test health check when service is healthy."""
        mock_model = Mock()
        mock_model.invoke.return_value = Mock()
        mock_chat_openai.return_value = mock_model

        service = OpenAIService(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )

        is_healthy, message = service.is_healthy()
        assert is_healthy is True
        assert message == "VLM service is healthy"

    @patch("src.services.vlm_service.openai_compatible.ChatOpenAI")
    def test_health_check_failure(self, mock_chat_openai):
        """Test health check when service fails."""
        mock_model = Mock()
        mock_model.invoke.side_effect = Exception("Connection error")
        mock_chat_openai.return_value = mock_model

        service = OpenAIService(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )

        is_healthy, message = service.is_healthy()
        assert is_healthy is False
        assert "Connection error" in message

    @patch("src.services.vlm_service.openai_compatible.ChatOpenAI")
    def test_generate_response_with_url(self, mock_chat_openai):
        """Test generating response with URL image."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = "This is a test image description"
        mock_model.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model

        service = OpenAIService(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )

        response = service.generate_response(
            image="http://example.com/image.jpg", prompt="Describe this image"
        )

        assert response == "This is a test image description"
        assert mock_model.invoke.called

    @patch("src.services.vlm_service.openai_compatible.ChatOpenAI")
    def test_generate_response_with_bytes(self, mock_chat_openai):
        """Test generating response with image bytes."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = "Image from bytes"
        mock_model.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model

        service = OpenAIService(
            temperature=0.7,
            top_p=0.9,
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )

        # Create fake image bytes
        fake_image_bytes = b"fake_image_data"

        response = service.generate_response(
            image=fake_image_bytes, prompt="What is in this image?"
        )

        assert response == "Image from bytes"
        assert mock_model.invoke.called


class TestVLMConfiguration:
    """Test VLM configuration integration."""

    def test_openai_service_with_custom_params(self):
        """Test OpenAI service with custom parameters."""
        service = OpenAIService(
            temperature=0.9,
            top_p=0.95,
            openai_api_key="custom_key",
            openai_api_base="http://custom.com/v1",
            model_name="custom_model",
        )

        assert service.temperature == 0.9
        assert service.top_p == 0.95
        assert service.openai_api_key == "custom_key"
        assert service.openai_api_base == "http://custom.com/v1"
        assert service.model_name == "custom_model"


# Integration test
class TestVLMIntegration:
    """Integration tests for the complete VLM system."""

    @patch("src.services.vlm_service.openai_compatible.ChatOpenAI")
    def test_full_integration_mock_api(self, mock_chat_openai):
        """Test full integration with mocked OpenAI API."""
        # Mock the chat model
        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = "A detailed description of the image"
        mock_model.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model

        # Initialize the service via factory
        vlm_service = VLMFactory.get_vlm_service(
            "openai_chat_agent",
            openai_api_key="test_key",
            openai_api_base="http://localhost:8001/v1",
            model_name="test_model",
        )

        # Test response generation
        result = vlm_service.generate_response(
            image="http://example.com/test.jpg", prompt="Describe this image"
        )

        # Verify result
        assert result == "A detailed description of the image"

        # Verify API call was made
        assert mock_model.invoke.called

        # Verify health check works
        is_healthy, message = vlm_service.is_healthy()
        assert is_healthy is True
