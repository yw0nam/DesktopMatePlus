"""
Manual test script for VLM API endpoint.

This script demonstrates how to use the VLM API endpoint
to analyze images using the vision-language model.
"""

import requests


def test_vlm_api():
    """Test the VLM API endpoint with a sample image."""
    base_url = "http://127.0.0.1:8000"

    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

    print()

    # Test 2: VLM analyze with URL
    print("2. Testing VLM analyze endpoint with image URL...")
    test_image_url = "https://external-preview.redd.it/shiki-natsume-v0-wBgSzBHXBZrzjI8f0mIQ_40-pe6069ikT9xnoNn2liA.jpg?auto=webp&s=3fdbd0ceb69cab6c2efc6dd68559ca7fa8a7d191"

    try:
        response = requests.post(
            f"{base_url}/v1/vlm/analyze",
            json={
                "image": test_image_url,
                "prompt": "Describe this image in detail",
            },
            timeout=30,
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Description: {result['description']}")
        else:
            print(f"   Error: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

    print()

    # Test 3: VLM analyze with base64 (small test image)
    print("3. Testing VLM analyze endpoint with base64 image...")
    # This is a 1x1 red pixel PNG
    base64_test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    try:
        response = requests.post(
            f"{base_url}/v1/vlm/analyze",
            json={
                "image": base64_test_image,
                "prompt": "What do you see in this image?",
            },
            timeout=30,
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Description: {result['description']}")
        else:
            print(f"   Error: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("VLM API Manual Test")
    print("=" * 60)
    print()
    print("Note: Make sure the server is running before executing this script.")
    print("Start server with: uv run python -m src.main")
    print()

    test_vlm_api()

    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)
