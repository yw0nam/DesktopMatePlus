"""
VLM Service Demo

This script demonstrates how to use the VLM service with OpenAI-compatible APIs.
It shows the new factory pattern interface for vision-language model inference.
"""

import logging
import os

from dotenv import load_dotenv

from src.services.vlm_service import VLMFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def demo_vlm_basic():
    """Demonstrate basic VLM usage with URL image."""
    print("=== Basic VLM Demo (URL Image) ===")

    # Initialize VLM engine using factory
    print("1. Initializing VLM engine...")
    vlm_engine = VLMFactory.get_vlm_service(
        "openai",
        openai_api_key=os.getenv("VLM_API_KEY"),
        openai_api_base=os.getenv("VLM_BASE_URL"),
        model_name=os.getenv("VLM_MODEL_NAME"),
    )
    print("✓ VLM engine initialized")

    # Check health
    print("\n2. Checking VLM service health...")
    is_healthy = vlm_engine.health_check()
    print(f"Health status: {is_healthy}")

    # Test VLM with URL image
    print("\n3. Testing VLM with URL image...")
    test_image_url = "https://external-preview.redd.it/shiki-natsume-v0-wBgSzBHXBZrzjI8f0mIQ_40-pe6069ikT9xnoNn2liA.jpg?auto=webp&s=3fdbd0ceb69cab6c2efc6dd68559ca7fa8a7d191"

    try:
        description = vlm_engine.generate_response(
            image=test_image_url, prompt="Describe this image in detail."
        )

        if description:
            print("✓ Success! Generated description:")
            print(f"  {description}")
        else:
            print("✗ Failed to generate description")

    except Exception as e:
        print(f"✗ Error: {e}")


def demo_vlm_with_bytes():
    """Demonstrate VLM usage with image bytes."""
    print("\n=== VLM Demo with Image Bytes ===")

    vlm_engine = VLMFactory.get_vlm_service(
        "openai",
        openai_api_key=os.getenv("VLM_API_KEY"),
        openai_api_base=os.getenv("VLM_BASE_URL"),
        model_name=os.getenv("VLM_MODEL_NAME"),
    )

    # Test with screen capture (if available)
    print("1. Attempting to capture screen...")
    try:
        from src.services.screen_capture_service import get_screen_capture_service

        screen_service = get_screen_capture_service()
        image_bytes = screen_service.capture_primary_screen()

        print(f"✓ Screen captured ({len(image_bytes)} bytes)")

        # Analyze the screen
        print("\n2. Analyzing screen content with VLM...")
        description = vlm_engine.generate_response(
            image=image_bytes,
            prompt="What do you see on this screen? Describe the main elements and content.",
        )

        if description:
            print("✓ Success! Screen analysis:")
            print(f"  {description}")
        else:
            print("✗ Failed to analyze screen")

    except Exception as e:
        print(f"⚠️  Screen capture not available: {e}")
        print("  (This is expected in headless environments)")


def demo_vlm_different_prompts():
    """Demonstrate VLM with different types of prompts."""
    print("\n=== VLM Demo with Different Prompts ===")

    vlm_engine = VLMFactory.get_vlm_service(
        "openai",
        openai_api_key=os.getenv("VLM_API_KEY"),
        openai_api_base=os.getenv("VLM_BASE_URL"),
        model_name=os.getenv("VLM_MODEL_NAME"),
    )

    test_image_url = "https://external-preview.redd.it/shiki-natsume-v0-wBgSzBHXBZrzjI8f0mIQ_40-pe6069ikT9xnoNn2liA.jpg?auto=webp&s=3fdbd0ceb69cab6c2efc6dd68559ca7fa8a7d191"

    prompts = [
        "Describe this image briefly.",
        "What is the main subject of this image?",
        "What colors are prominent in this image?",
        "Is there any text visible in this image?",
    ]

    for i, prompt in enumerate(prompts, 1):
        print(f"\n{i}. Prompt: '{prompt}'")
        try:
            response = vlm_engine.generate_response(image=test_image_url, prompt=prompt)
            print(
                f"   Response: {response[:100]}..."
                if len(response) > 100
                else f"   Response: {response}"
            )
        except Exception as e:
            print(f"   Error: {e}")


def main():
    """Run all demos."""
    print("VLM Service Demo - OpenAI Compatible API")
    print("=" * 60)

    # Check environment variables
    required_vars = ["VLM_API_KEY", "VLM_BASE_URL", "VLM_MODEL_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set them in your .env file.")
        return

    try:
        # Demo 1: Basic VLM with URL
        demo_vlm_basic()

        # Demo 2: VLM with image bytes (screen capture)
        demo_vlm_with_bytes()

        # Demo 3: Different prompts
        demo_vlm_different_prompts()

        print("\n" + "=" * 60)
        print("🎉 All demos completed!")
        print(f"\nNote: VLM service at {os.getenv('VLM_BASE_URL')}")
        print("If you see errors, check that the VLM service is running.")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        print("\nMake sure to:")
        print("1. Set VLM_API_KEY, VLM_BASE_URL, VLM_MODEL_NAME in .env")
        print("2. Start VLM service at the configured URL")
        print("3. Verify network connectivity")


if __name__ == "__main__":
    main()
