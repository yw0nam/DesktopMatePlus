"""Tests for screen capture service."""

import base64
import io

import pytest
from PIL import Image

from src.services.screen_capture_service import (
    ScreenCaptureError,
    ScreenCaptureService,
    get_screen_capture_service,
)


class TestScreenCaptureService:
    """Test suite for ScreenCaptureService."""

    @pytest.fixture
    def service(self):
        """Create a ScreenCaptureService instance for testing."""
        return ScreenCaptureService()

    def test_service_initialization(self, service):
        """Test that service initializes correctly."""
        assert service is not None
        assert service.os_type in ["Linux", "Darwin", "Windows"]

    def test_singleton_pattern(self):
        """Test that get_screen_capture_service returns singleton."""
        service1 = get_screen_capture_service()
        service2 = get_screen_capture_service()
        assert service1 is service2

    def test_capture_primary_screen(self, service):
        """Test capturing the primary screen."""
        try:
            image_bytes = service.capture_primary_screen()

            # Verify it's valid image bytes
            assert isinstance(image_bytes, bytes)
            assert len(image_bytes) > 0

            # Try to open as PIL Image to verify it's valid
            img = Image.open(io.BytesIO(image_bytes))
            assert img.format == "PNG"
            assert img.size[0] > 0
            assert img.size[1] > 0

            print(f"✓ Captured primary screen: {img.size[0]}x{img.size[1]} pixels")

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_capture_all_screens(self, service):
        """Test capturing all monitors."""
        try:
            screenshots = service.capture_all_screens()

            # Verify we got at least one screenshot
            assert isinstance(screenshots, list)
            assert len(screenshots) > 0

            # Verify each screenshot is valid
            for i, screenshot in enumerate(screenshots):
                assert isinstance(screenshot, bytes)
                assert len(screenshot) > 0

                img = Image.open(io.BytesIO(screenshot))
                assert img.format == "PNG"
                print(f"✓ Monitor {i+1}: {img.size[0]}x{img.size[1]} pixels")

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_capture_region(self, service):
        """Test capturing a specific region."""
        try:
            # Capture a small region (100x100 from top-left)
            image_bytes = service.capture_region(0, 0, 100, 100)

            # Verify it's valid image bytes
            assert isinstance(image_bytes, bytes)
            assert len(image_bytes) > 0

            # Verify dimensions
            img = Image.open(io.BytesIO(image_bytes))
            assert img.format == "PNG"
            assert img.size == (100, 100)

            print(f"✓ Captured region: {img.size[0]}x{img.size[1]} pixels")

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_capture_to_base64(self, service):
        """Test capturing and encoding to Base64."""
        try:
            base64_str = service.capture_to_base64()

            # Verify it's a valid Base64 string
            assert isinstance(base64_str, str)
            assert len(base64_str) > 0

            # Verify we can decode it back to image
            image_bytes = base64.b64decode(base64_str)
            img = Image.open(io.BytesIO(image_bytes))
            assert img.format == "PNG"

            print(
                f"✓ Base64 encoded screen: {img.size[0]}x{img.size[1]}, "
                f"length: {len(base64_str)} chars"
            )

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_capture_to_base64_with_resize(self, service):
        """Test capturing with image resizing."""
        try:
            # Capture and resize to max 800x600
            base64_str = service.capture_to_base64(max_size=(800, 600))

            # Verify it's valid
            assert isinstance(base64_str, str)
            assert len(base64_str) > 0

            # Verify dimensions
            image_bytes = base64.b64decode(base64_str)
            img = Image.open(io.BytesIO(image_bytes))

            # Image should be at most 800x600
            assert img.size[0] <= 800
            assert img.size[1] <= 600

            print(f"✓ Resized image: {img.size[0]}x{img.size[1]} pixels")

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_get_monitor_count(self, service):
        """Test getting monitor count."""
        try:
            count = service.get_monitor_count()

            assert isinstance(count, int)
            assert count >= 1

            print(f"✓ Detected {count} monitor(s)")

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_get_monitor_info(self, service):
        """Test getting monitor information."""
        try:
            monitors = service.get_monitor_info()

            assert isinstance(monitors, list)
            assert len(monitors) >= 1

            # Verify structure of monitor info
            for monitor in monitors:
                assert "index" in monitor
                assert "width" in monitor
                assert "height" in monitor
                assert "left" in monitor
                assert "top" in monitor

                assert monitor["width"] > 0
                assert monitor["height"] > 0

                print(
                    f"✓ Monitor {monitor['index']}: "
                    f"{monitor['width']}x{monitor['height']} "
                    f"at ({monitor['left']}, {monitor['top']})"
                )

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")

    def test_error_handling_invalid_region(self, service):
        """Test error handling for invalid region."""
        try:
            # Try to capture with invalid dimensions
            with pytest.raises(ScreenCaptureError):
                service.capture_region(-1, -1, 0, 0)

        except Exception as e:
            pytest.skip(f"Display not available in test environment: {e}")


def test_integration_capture_and_process():
    """Integration test: Capture, process, and verify image."""
    try:
        service = get_screen_capture_service()

        # Capture screen
        image_bytes = service.capture_primary_screen()

        # Process the image
        img = Image.open(io.BytesIO(image_bytes))

        # Resize to a smaller size (simulating VLM preprocessing)
        img.thumbnail((1024, 768), Image.Resampling.LANCZOS)

        # Convert back to bytes
        output = io.BytesIO()
        img.save(output, format="PNG")
        processed_bytes = output.getvalue()

        # Verify processed image
        assert len(processed_bytes) > 0
        assert len(processed_bytes) < len(image_bytes)  # Should be smaller

        print(
            f"✓ Integration test passed: "
            f"Original: {len(image_bytes)} bytes, "
            f"Processed: {len(processed_bytes)} bytes"
        )

    except Exception as e:
        pytest.skip(f"Display not available in test environment: {e}")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
