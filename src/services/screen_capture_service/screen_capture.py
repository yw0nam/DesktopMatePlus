"""
Screen capture utility for DesktopMate+ backend.

This module provides cross-platform screen capture functionality:
- Uses MSS for cross-platform support (Windows, macOS, Linux)
- Supports full screen and region capture
- Returns images as bytes for API transmission
- Includes Base64 encoding for VLM API compatibility
"""

import base64
import io
import platform
from typing import Optional, Tuple

import mss
from loguru import logger
from PIL import Image


class ScreenCaptureError(Exception):
    """Raised when screen capture fails."""

    pass


class ScreenCaptureService:
    """
    Cross-platform screen capture service.

    Uses MSS library for efficient screen capturing on all platforms.
    """

    def __init__(self):
        """Initialize the screen capture service."""
        self.os_type = platform.system()
        logger.info(f"ScreenCaptureService initialized for {self.os_type}")

    def capture_primary_screen(self) -> bytes:
        """
        Capture the primary monitor screen.

        Returns:
            bytes: PNG image data as bytes

        Raises:
            ScreenCaptureError: If screen capture fails
        """
        try:
            with mss.mss() as sct:
                # Capture the first monitor (primary display)
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

                # Convert to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                logger.debug(
                    f"Captured primary screen: {screenshot.size[0]}x{screenshot.size[1]}"
                )
                return img_bytes.getvalue()

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            raise ScreenCaptureError(f"Screen capture failed: {e}") from e

    def capture_all_screens(self) -> list[bytes]:
        """
        Capture all monitors.

        Returns:
            list[bytes]: List of PNG image data as bytes for each monitor

        Raises:
            ScreenCaptureError: If screen capture fails
        """
        try:
            screenshots = []
            with mss.mss() as sct:
                # Skip index 0 (all monitors combined)
                for i, monitor in enumerate(sct.monitors[1:], start=1):
                    screenshot = sct.grab(monitor)

                    # Convert to PIL Image
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

                    # Convert to bytes
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format="PNG")
                    img_bytes.seek(0)

                    screenshots.append(img_bytes.getvalue())
                    logger.debug(
                        f"Captured monitor {i}: {screenshot.size[0]}x{screenshot.size[1]}"
                    )

            logger.info(f"Captured {len(screenshots)} monitors")
            return screenshots

        except Exception as e:
            logger.error(f"Failed to capture screens: {e}")
            raise ScreenCaptureError(f"Screen capture failed: {e}") from e

    def capture_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """
        Capture a specific region of the screen.

        Args:
            x: Left coordinate
            y: Top coordinate
            width: Width of the region
            height: Height of the region

        Returns:
            bytes: PNG image data as bytes

        Raises:
            ScreenCaptureError: If screen capture fails
        """
        try:
            with mss.mss() as sct:
                # Define the region to capture
                monitor = {"top": y, "left": x, "width": width, "height": height}
                screenshot = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

                # Convert to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                logger.debug(f"Captured region: {x},{y} {width}x{height}")
                return img_bytes.getvalue()

        except Exception as e:
            logger.error(f"Failed to capture region: {e}")
            raise ScreenCaptureError(f"Region capture failed: {e}") from e

    def capture_to_base64(
        self, monitor_index: int = 1, max_size: Optional[Tuple[int, int]] = None
    ) -> str:
        """
        Capture screen and return as Base64 encoded string.

        This is useful for VLM API requests that accept Base64 encoded images.

        Args:
            monitor_index: Monitor number to capture (1 = primary)
            max_size: Optional (width, height) tuple to resize image

        Returns:
            str: Base64 encoded PNG image

        Raises:
            ScreenCaptureError: If screen capture fails
        """
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[monitor_index]
                screenshot = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

                # Resize if max_size is specified
                if max_size:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    logger.debug(f"Resized image to {img.size}")

                # Convert to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG", optimize=True)
                img_bytes.seek(0)

                # Encode to Base64
                base64_str = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

                logger.debug(
                    f"Captured and encoded screen to Base64 (length: {len(base64_str)})"
                )
                return base64_str

        except Exception as e:
            logger.error(f"Failed to capture and encode screen: {e}")
            raise ScreenCaptureError(f"Base64 capture failed: {e}") from e

    def get_monitor_count(self) -> int:
        """
        Get the number of monitors connected.

        Returns:
            int: Number of monitors
        """
        try:
            with mss.mss() as sct:
                # Subtract 1 because index 0 is all monitors combined
                count = len(sct.monitors) - 1
                logger.debug(f"Detected {count} monitors")
                return count
        except Exception as e:
            logger.error(f"Failed to get monitor count: {e}")
            return 1  # Default to 1 monitor

    def get_monitor_info(self) -> list[dict]:
        """
        Get information about all monitors.

        Returns:
            list[dict]: List of monitor information dicts with keys:
                        'index', 'width', 'height', 'left', 'top'
        """
        try:
            monitors_info = []
            with mss.mss() as sct:
                for i, monitor in enumerate(sct.monitors[1:], start=1):
                    info = {
                        "index": i,
                        "width": monitor["width"],
                        "height": monitor["height"],
                        "left": monitor["left"],
                        "top": monitor["top"],
                    }
                    monitors_info.append(info)

            logger.debug(f"Retrieved info for {len(monitors_info)} monitors")
            return monitors_info

        except Exception as e:
            logger.error(f"Failed to get monitor info: {e}")
            return []


# Singleton instance
_screen_capture_service: Optional[ScreenCaptureService] = None


def get_screen_capture_service() -> ScreenCaptureService:
    """
    Get or create the singleton ScreenCaptureService instance.

    Returns:
        ScreenCaptureService: The screen capture service instance
    """
    global _screen_capture_service
    if _screen_capture_service is None:
        _screen_capture_service = ScreenCaptureService()
    return _screen_capture_service
