"""
Example: Integrating screen capture with VLM service.

This shows how to capture the screen and prepare it for VLM API requests.
"""

import asyncio
from typing import Any, Dict

from src.services.screen_capture_service import get_screen_capture_service


async def prepare_screen_context_for_vlm() -> Dict[str, Any]:
    """
    Capture current screen and prepare for VLM API request.

    Returns:
        Dict with image data in format ready for VLM API
    """
    service = get_screen_capture_service()

    # Capture screen and encode to Base64
    # Resize to reasonable size for API (1280x720 max)
    base64_image = service.capture_to_base64(max_size=(1280, 720))

    # Format for VLM API (OpenAI Vision format)
    image_data = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }

    return image_data


async def get_visual_description(prompt: str = "What do you see on the screen?") -> str:
    """
    Get a visual description of the current screen using VLM.

    This is a placeholder showing the integration pattern.
    The actual VLM API call will be implemented in the VLM service.

    Args:
        prompt: Question or instruction for the VLM

    Returns:
        Description of the screen content
    """
    # Capture screen
    _image_data = await prepare_screen_context_for_vlm()

    # In actual implementation, this would call the VLM service:
    # from src.services.vlm_service import get_vlm_client
    # vlm_client = get_vlm_client()
    # response = await vlm_client.analyze(image_data, prompt)
    # return response

    # Placeholder response
    return f"[VLM would analyze the image with prompt: '{prompt}']"


async def example_langgraph_tool():
    """
    Example of how screen capture would be used as a LangGraph tool.

    This would be called from the LangGraph agent's perceive_environment node.
    """
    print("LangGraph Tool: get_screen_context")
    print("-" * 60)

    # Tool execution
    try:
        service = get_screen_capture_service()

        # Capture and prepare for VLM
        base64_image = service.capture_to_base64(max_size=(1024, 768))

        print("✓ Screen captured and encoded")
        print(f"✓ Base64 length: {len(base64_image)} chars")
        print("✓ Ready for VLM API call")

        # This image would be sent to VLM for analysis
        # and the description would be stored in GraphState.visual_context

        return {
            "success": True,
            "image_size": len(base64_image),
            "format": "base64_png",
        }

    except Exception as e:
        print(f"✗ Tool failed: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Run integration examples."""
    print("=" * 60)
    print("Screen Capture + VLM Integration Examples")
    print("=" * 60)
    print()

    # Example 1: Prepare for VLM
    print("Example 1: Prepare screen context for VLM")
    print("-" * 60)
    try:
        image_data = await prepare_screen_context_for_vlm()
        print("✓ Image prepared for VLM API")
        print(f"✓ Format: {image_data['type']}")
        print(f"✓ URL prefix: {image_data['image_url']['url'][:50]}...")
        print()
    except Exception as e:
        print(f"✗ Failed: {e}")
        print()

    # Example 2: LangGraph tool pattern
    print("Example 2: LangGraph Tool Pattern")
    print("-" * 60)
    result = await example_langgraph_tool()
    print(f"Tool result: {result}")
    print()

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
