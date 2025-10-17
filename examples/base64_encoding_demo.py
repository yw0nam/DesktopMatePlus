"""
Integration example: Screen capture to VLM API format.

This demonstrates the complete flow:
1. Capture screen using ScreenCaptureService
2. Encode image to Base64 using VLM utils
3. Prepare image for VLM API request
"""

import sys
from pathlib import Path

# Add src to path for running as standalone script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.screen_capture_service import get_screen_capture_service
from src.services.vlm_service.utils import prepare_image_for_vlm


def example_capture_and_encode():
    """Example: Capture screen and encode for VLM API."""
    print("=" * 60)
    print("Screen Capture → Base64 Encoding → VLM Format")
    print("=" * 60)
    print()

    # Step 1: Capture screen
    print("Step 1: Capturing screen...")
    service = get_screen_capture_service()
    image_bytes = service.capture_primary_screen()
    print(f"✓ Captured {len(image_bytes)} bytes")
    print()

    # Step 2: Prepare for VLM API
    print("Step 2: Preparing for VLM API...")
    vlm_input = prepare_image_for_vlm(image_bytes, mime_type="image/png")
    print("✓ Image prepared for VLM")
    print(f"  - Type: {vlm_input['type']}")
    print(f"  - Source: {vlm_input['source_type']}")
    print(f"  - MIME: {vlm_input['mime_type']}")
    print(f"  - Base64 length: {len(vlm_input['data'])} chars")
    print()

    # Step 3: Alternative - Use built-in base64 method
    print("Step 3: Alternative using capture_to_base64()...")
    base64_str = service.capture_to_base64(max_size=(1280, 720))
    print(f"✓ Direct Base64 capture: {len(base64_str)} chars")
    print()

    return vlm_input


def example_with_url():
    """Example: Prepare URL for VLM API."""
    print("=" * 60)
    print("URL Image → VLM Format")
    print("=" * 60)
    print()

    url = "https://example.com/screenshot.png"
    vlm_input = prepare_image_for_vlm(url)

    print("✓ URL prepared for VLM")
    print(f"  - Type: {vlm_input['type']}")
    print(f"  - Source: {vlm_input['source_type']}")
    print(f"  - URL: {vlm_input['url']}")
    print()

    return vlm_input


def example_integration_with_vlm_service():
    """Example: Complete integration with VLM service."""
    print("=" * 60)
    print("Complete VLM Service Integration")
    print("=" * 60)
    print()

    # This is how it would be used with BaseVLMService.generate_response()
    # The service accepts both bytes and URL strings:
    #
    from src.services.vlm_service import get_vlm_service

    service = get_screen_capture_service()
    image_bytes = service.capture_primary_screen()
    vlm = get_vlm_service()
    response = vlm.generate_response(
        prompt="What do you see on the screen?",
        image=image_bytes,  # or image=url_string
    )
    print("✓ Integration pattern demonstrated")
    print(response)
    print("Usage example:")
    print("  service = get_screen_capture_service()")
    print("  image_bytes = service.capture_primary_screen()")
    print("  vlm = get_vlm_service()")
    print("  response = vlm.generate_response(")
    print("      prompt='What do you see on the screen?',")
    print("      image=image_bytes  # BaseVLMService handles encoding")
    print("  )")
    print()


if __name__ == "__main__":
    try:
        # Example 1: Screen capture and encode
        example_capture_and_encode()

        # Example 2: URL preparation
        example_with_url()

        # Example 3: VLM service integration
        example_integration_with_vlm_service()

        print("=" * 60)
        print("✓ All examples completed successfully")
        print("=" * 60)

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
