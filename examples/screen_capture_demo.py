"""
Demo script for screen capture service.

Run this script in an environment with a display to test the screen capture functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.screen_capture_service import get_screen_capture_service


def main():
    """Demo the screen capture functionality."""
    print("=" * 60)
    print("DesktopMate+ Screen Capture Demo")
    print("=" * 60)
    print()

    # Get service instance
    service = get_screen_capture_service()
    print(f"✓ Service initialized for: {service.os_type}")
    print()

    # Get monitor information
    print("Monitor Information:")
    print("-" * 60)
    try:
        monitors = service.get_monitor_info()
        for monitor in monitors:
            print(
                f"  Monitor {monitor['index']}: "
                f"{monitor['width']}x{monitor['height']} "
                f"at ({monitor['left']}, {monitor['top']})"
            )
        print()
    except Exception as e:
        print(f"  ⚠ Could not get monitor info: {e}")
        print()

    # Test primary screen capture
    print("Testing Primary Screen Capture:")
    print("-" * 60)
    try:
        image_bytes = service.capture_primary_screen()
        print(f"  ✓ Captured {len(image_bytes)} bytes")
        print(f"  ✓ Image size: {len(image_bytes) / 1024:.2f} KB")

        # Save to file
        output_path = Path("screenshot_primary.png")
        output_path.write_bytes(image_bytes)
        print(f"  ✓ Saved to: {output_path.absolute()}")
        print()
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print()

    # Test Base64 encoding
    print("Testing Base64 Encoding:")
    print("-" * 60)
    try:
        base64_str = service.capture_to_base64(max_size=(1024, 768))
        print(f"  ✓ Encoded to Base64")
        print(f"  ✓ Base64 length: {len(base64_str)} characters")
        print(f"  ✓ Preview (first 100 chars): {base64_str[:100]}...")
        print()
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print()

    # Test region capture
    print("Testing Region Capture (top-left 400x300):")
    print("-" * 60)
    try:
        region_bytes = service.capture_region(0, 0, 400, 300)
        print(f"  ✓ Captured region: {len(region_bytes)} bytes")

        # Save to file
        output_path = Path("screenshot_region.png")
        output_path.write_bytes(region_bytes)
        print(f"  ✓ Saved to: {output_path.absolute()}")
        print()
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print()

    # Test all screens capture
    print("Testing All Screens Capture:")
    print("-" * 60)
    try:
        screenshots = service.capture_all_screens()
        print(f"  ✓ Captured {len(screenshots)} monitor(s)")

        for i, screenshot in enumerate(screenshots, start=1):
            output_path = Path(f"screenshot_monitor_{i}.png")
            output_path.write_bytes(screenshot)
            print(
                f"  ✓ Monitor {i}: {len(screenshot) / 1024:.2f} KB "
                f"saved to {output_path}"
            )
        print()
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print()

    print("=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
