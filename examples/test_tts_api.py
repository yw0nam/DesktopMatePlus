#!/usr/bin/env python3
"""Quick test to verify TTS API is working."""

import asyncio
import base64
import sys

import httpx


async def test_tts_api():
    """Test if TTS API is accessible and working."""
    url = "http://localhost:8000/v1/tts/synthesize"

    print("Testing TTS API...")
    print(f"URL: {url}\n")

    payload = {
        "text": "Hello, this is a test.",
        "output_format": "base64",
        "reference_id": "ナツメ",  # Use ナツメ voice
    }

    try:
        async with httpx.AsyncClient() as client:
            print(f"Sending request: {payload}")
            response = await client.post(url, json=payload, timeout=30.0)

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Response keys: {list(result.keys())}")

                audio_data = result.get("audio_data")
                if audio_data:
                    audio_bytes = base64.b64decode(audio_data)
                    print(f"✅ Success! Got {len(audio_bytes)} bytes of audio")

                    # Save to file
                    with open("test_tts_output.wav", "wb") as f:
                        f.write(audio_bytes)
                    print("✅ Saved to test_tts_output.wav")
                    return True
                else:
                    print(f"❌ No audio_data in response: {result}")
                    return False
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                return False

    except httpx.ConnectError as e:
        print(f"❌ Cannot connect to TTS service: {e}")
        print("\nMake sure the server is running:")
        print("  uv run python -m src.main --yaml_file ./yaml_files/main.yml --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_tts_api())
    sys.exit(0 if success else 1)
