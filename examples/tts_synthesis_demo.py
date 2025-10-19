"""
TTS Synthesis Demo

This script demonstrates how to use the TTS service with Fish Speech.
It shows the new factory pattern interface for TTS synthesis.
"""

import logging
from pathlib import Path

from src.services.tts_service import TTSFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_tts_basic():
    """Demonstrate basic TTS usage."""
    print("=== Basic TTS Demo ===")

    # Initialize TTS engine using factory
    print("1. Initializing TTS engine...")
    tts_engine = TTSFactory.get_tts_engine(
        "fish_local_tts", base_url="http://localhost:8080/v1/tts"
    )
    print("✓ TTS engine initialized")

    # Check health
    print("\n2. Checking TTS service health...")
    is_healthy, message = tts_engine.is_healthy()
    print(f"Health status: {is_healthy} - {message}")

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
            # Use the engine to generate speech
            audio_bytes = tts_engine.generate_speech(text, output_format="bytes")

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


def demo_different_formats():
    """Demonstrate different output formats."""
    print("\n=== Different Output Formats Demo ===")

    tts_engine = TTSFactory.get_tts_engine(
        "fish_local_tts", base_url="http://localhost:8080/v1/tts"
    )

    text = "Testing different output formats."

    # Test bytes format (default)
    print("1. Testing bytes format...")
    result = tts_engine.generate_speech(text, output_format="bytes")
    if result:
        print(f"✓ Bytes format: {len(result)} bytes")

    # Test base64 format
    print("\n2. Testing base64 format...")
    base64_result = tts_engine.generate_speech(text, output_format="base64")
    if base64_result:
        print(f"✓ Base64 format: {len(base64_result)} characters")
        print(f"Sample: {base64_result[:50]}...")

    # Test file format
    print("\n3. Testing file format...")
    file_result = tts_engine.generate_speech(
        text, output_format="file", output_filename="format_demo.wav"
    )
    if file_result:
        print("✓ File format: Saved to format_demo.wav")

        # Check file size
        file_path = Path("format_demo.wav")
        if file_path.exists():
            print(f"File size: {file_path.stat().st_size} bytes")


def demo_with_reference():
    """Demonstrate TTS with reference voice."""
    print("\n=== TTS with Reference Voice Demo ===")

    tts_engine = TTSFactory.get_tts_engine(
        "fish_local_tts", base_url="http://localhost:8080/v1/tts"
    )

    text = "This uses a specific reference voice."
    reference_id = "ナツメ"  # Example reference voice ID

    print(f"Generating speech with reference: {reference_id}")
    result = tts_engine.generate_speech(
        text, reference_id=reference_id, output_format="bytes"
    )

    if result:
        print(f"✓ Success! Generated {len(result)} bytes with reference voice")
        output_file = Path("reference_voice_demo.wav")
        with open(output_file, "wb") as f:
            f.write(result)
        print(f"✓ Saved to {output_file}")
    else:
        print("✗ Failed to generate audio with reference voice")


def main():
    """Run all demos."""
    print("TTS Service Demo - Fish Speech Integration")
    print("=" * 50)

    try:
        # Demo 1: Basic TTS
        demo_tts_basic()

        # Demo 2: Different formats
        demo_different_formats()

        # Demo 3: With reference voice
        demo_with_reference()

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
