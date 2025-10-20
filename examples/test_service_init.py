"""Test script to verify service initialization."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path before importing application modules
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from src.services import (  # noqa: E402
    get_tts_service,
    get_vlm_service,
    initialize_tts_service,
    initialize_vlm_service,
)

load_dotenv()


def main():
    print("=" * 60)
    print("Testing Service Initialization")
    print("=" * 60)

    # Show environment variables
    print("\n0. Environment Variables:")
    print(f"   VLM_BASE_URL: {os.getenv('VLM_BASE_URL', 'Not set')}")
    print(f"   VLM_MODEL_NAME: {os.getenv('VLM_MODEL_NAME', 'Not set')}")
    print(f"   VLM_API_KEY: {'Set' if os.getenv('VLM_API_KEY') else 'Not set'}")
    print(f"   TTS_BASE_URL: {os.getenv('TTS_BASE_URL', 'Not set')}")
    print(f"   TTS_API_KEY: {'Set' if os.getenv('TTS_API_KEY') else 'Not set'}")

    # Test TTS initialization
    print("\n1. Initializing TTS service...")
    try:
        tts_service = initialize_tts_service()
        print(f"✅ TTS service initialized: {type(tts_service).__name__}")
    except Exception as e:
        print(f"❌ Failed to initialize TTS service: {e}")
        import traceback

        traceback.print_exc()
        tts_service = None

    # Test VLM initialization
    print("\n2. Initializing VLM service...")
    try:
        vlm_service = initialize_vlm_service()
        print(f"✅ VLM service initialized: {type(vlm_service).__name__}")
    except Exception as e:
        print(f"❌ Failed to initialize VLM service: {e}")
        import traceback

        traceback.print_exc()
        vlm_service = None

    # Test getter functions
    print("\n3. Testing getter functions...")
    tts = get_tts_service()
    vlm = get_vlm_service()

    if tts is not None:
        print(f"✅ TTS service retrieved: {type(tts).__name__}")
    else:
        print("❌ TTS service is None")

    if vlm is not None:
        print(f"✅ VLM service retrieved: {type(vlm).__name__}")
    else:
        print("❌ VLM service is None")

    # Test health checks
    print("\n4. Testing health checks...")
    if tts:
        try:
            tts_healthy, tts_msg = tts.is_healthy()
            print(f"TTS Health: {'✅' if tts_healthy else '❌'} - {tts_msg}")
        except Exception as e:
            print(f"❌ TTS health check failed: {e}")

    if vlm:
        try:
            vlm_healthy, vlm_msg = vlm.is_healthy()
            print(f"VLM Health: {'✅' if vlm_healthy else '❌'} - {vlm_msg}")
        except Exception as e:
            print(f"❌ VLM health check failed: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
