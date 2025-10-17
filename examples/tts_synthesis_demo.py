"""
TTS Synthesis Demo

This script demonstrates how to use the TTS service with Fish Speech.
It shows the main interface expected by task 8: synthesize_speech(text: str) -> bytes
"""

import logging
from pathlib import Path

from src.services.tts_service import (
    get_tts_client,
    initialize_tts_client,
    synthesize_speech,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_tts_client():
    """Demonstrate TTS client usage."""
    print("=== TTS Client Demo ===")

    # Initialize TTS client with Fish Speech
    print("1. Initializing TTS client...")
    client = initialize_tts_client(fish_speech_url="http://localhost:8080/v1/tts")
    print("✓ TTS client initialized")

    # Check health
    print("\n2. Checking TTS service health...")
    health = client.is_healthy()
    print(f"Health status: {health}")

    # Test speech synthesis
    test_texts = [
        "Hello, this is a test of the Fish Speech TTS system.",
        "The quick brown fox jumps over the lazy dog.",
        "(excited) This is amazing! The TTS system is working perfectly!",
    ]

    print("\n3. Testing speech synthesis...")
    for i, text in enumerate(test_texts, 1):
        print(f"\nTest {i}: '{text[:50]}...' ")

        try:
            # Use the client method
            audio_bytes = client.synthesize_speech(text)

            if audio_bytes:
                print(f"✓ Success! Generated {len(audio_bytes)} bytes of audio")

                # Save to file for verification
                output_file = Path(f"demo_output_{i}.wav")
                with open(output_file, "wb") as f:
                    f.write(audio_bytes)
                print(f"✓ Saved to {output_file}")
            else:
                print("✗ Failed to generate audio")

        except Exception as e:
            print(f"✗ Error: {e}")


def demo_global_function():
    """Demonstrate the global synthesize_speech function (task 8 requirement)."""
    print("\n=== Global Function Demo (Task 8) ===")

    # This is the main function required by task 8
    print("Testing synthesize_speech(text: str) -> bytes function...")

    test_text = "This demonstrates the main function required by task 8."

    try:
        # Use the global convenience function
        audio_bytes = synthesize_speech(test_text)

        if audio_bytes:
            print(f"✓ Success! synthesize_speech() returned {len(audio_bytes)} bytes")

            # Save demonstration file
            output_file = Path("task8_demo_output.wav")
            with open(output_file, "wb") as f:
                f.write(audio_bytes)
            print(f"✓ Task 8 demo output saved to {output_file}")
        else:
            print("✗ synthesize_speech() returned None")

    except Exception as e:
        print(f"✗ Error in synthesize_speech(): {e}")


def demo_different_formats():
    """Demonstrate different output formats."""
    print("\n=== Different Output Formats Demo ===")

    client = get_tts_client()
    text = "Testing different output formats."

    # Test bytes format (default)
    print("1. Testing bytes format...")
    result = client.synthesize_speech(text)
    if result:
        print(f"✓ Bytes format: {len(result)} bytes")

    # Test service directly for other formats
    service = client._service

    # Test base64 format
    print("\n2. Testing base64 format...")
    base64_result = service.synthesize_speech(text=text, output_format="base64")
    if base64_result:
        print(f"✓ Base64 format: {len(base64_result)} characters")
        print(f"Sample: {base64_result[:50]}...")

    # Test file format
    print("\n3. Testing file format...")
    file_result = service.synthesize_speech(
        text=text, output_format="file", output_filename="format_demo.wav"
    )
    if file_result:
        print("✓ File format: Saved to format_demo.wav")

        # Check file size
        file_path = Path("format_demo.wav")
        if file_path.exists():
            print(f"File size: {file_path.stat().st_size} bytes")


def main():
    """Run all demos."""
    print("TTS Service Demo - Fish Speech Integration")
    print("=" * 50)

    try:
        # Demo 1: TTS Client
        demo_tts_client()

        # Demo 2: Global function (task 8 requirement)
        demo_global_function()

        # Demo 3: Different formats
        demo_different_formats()

        print("\n" + "=" * 50)
        print("🎉 All demos completed successfully!")
        print(
            "\nNote: This demo assumes Fish Speech TTS is running at http://localhost:8080"
        )
        print("If the service is not available, you'll see connection errors.")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        print("\nMake sure to:")
        print("1. Start Fish Speech TTS server at http://localhost:8080")
        print("2. Check network connectivity")
        print("3. Verify all dependencies are installed")


if __name__ == "__main__":
    main()
