"""
Real-time TTS Streaming Demo

This example demonstrates the complete TTS streaming pipeline:
1. Connect to WebSocket API
2. Send a chat message (optionally with images)
3. Receive streaming tokens from the agent
4. Receive TTS chunks as sentences are completed (real-time)
5. Print each TTS chunk
6. Save TTS audio to WAV files

Expected behavior:
- TTS chunks arrive WHILE the agent is still streaming (not after)
- Each complete sentence triggers a TTS chunk immediately
- Audio files are saved incrementally as they arrive
- Images can be provided as file paths or URLs
"""

import argparse
import asyncio
import base64
import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import websockets


class RealtimeTTSDemo:
    """Demo client for real-time TTS streaming with optional image support."""

    def __init__(
        self,
        websocket_url: str = "ws://localhost:8000/v1/chat/stream",
        tts_url: str = "http://localhost:8000/v1/tts/synthesize",
        output_dir: str = "./tts_output",
        token: str = "demo-token",
        reference_id: str = "ナツメ",
        images: list[str] | None = None,
    ):
        self.websocket_url = websocket_url
        self.tts_url = tts_url
        self.output_dir = Path(output_dir)
        self.token = token
        self.reference_id = reference_id
        self.images = images or []
        self.chunk_count = 0
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {self.output_dir.absolute()}")
        print(f"🎙️  Reference voice: {self.reference_id}")
        if self.images:
            print(f"🖼️  Images to include: {len(self.images)}")

    def _load_image_as_base64(self, image_path: str) -> str | None:
        """
        Load an image file and convert to base64 data URL.

        Args:
            image_path: Path to local image file

        Returns:
            Base64 data URL string or None if failed
        """
        try:
            path = Path(image_path)
            if not path.exists():
                print(f"⚠️  Image file not found: {image_path}")
                return None

            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"  # Default fallback

            # Read and encode
            with open(path, "rb") as f:
                image_bytes = f.read()

            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"

        except Exception as e:
            print(f"❌ Failed to load image {image_path}: {e}")
            return None

    def _prepare_images(self) -> list[str]:
        """
        Prepare images for the chat message.

        Handles both:
        - URLs (http://, https://) - passed through as-is
        - Local file paths - converted to base64 data URLs

        Returns:
            List of image strings (URLs or base64 data URLs)
        """
        prepared = []
        for img in self.images:
            if img.startswith(("http://", "https://", "data:")):
                # Already a URL or data URL, use as-is
                prepared.append(img)
                print(
                    f"  🌐 Using URL: {img[:80]}..."
                    if len(img) > 80
                    else f"  🌐 Using URL: {img}"
                )
            else:
                # Assume it's a local file path
                base64_url = self._load_image_as_base64(img)
                if base64_url:
                    prepared.append(base64_url)
                    print(f"  📄 Loaded file: {img}")
        return prepared

    async def send_json(self, websocket: Any, payload: dict):
        """Send JSON message to websocket."""
        message = json.dumps(payload)
        await websocket.send(message)
        print(f">> {payload['type']}")

    async def synthesize_tts(
        self, text: str, emotion: str | None = None
    ) -> bytes | None:
        """Call TTS API to synthesize speech and return WAV audio."""
        payload = {
            "text": text,
            "output_format": "base64",  # Request base64 format
            "reference_id": self.reference_id,  # Use specified reference voice
        }
        if emotion:
            # Note: The TTS API might not support emotion parameter directly
            # You may need to embed it in the text like: "(joyful) text"
            pass

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.tts_url,
                    json=payload,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    # TTS API returns base64 encoded audio in 'audio_data' field
                    audio_base64 = result.get("audio_data")
                    if audio_base64:
                        audio_bytes = base64.b64decode(audio_base64)
                        return audio_bytes
                    else:
                        print(f"❌ No audio_data in response: {result}")
                        return None
                else:
                    error_text = response.text
                    print(
                        f"❌ TTS API error {response.status_code}: {error_text[:200]}"
                    )
                    return None
        except httpx.ConnectError as e:
            print(f"❌ Cannot connect to TTS service: {e}")
            return None
        except httpx.TimeoutException as e:
            print(f"❌ TTS request timeout: {e}")
            return None
        except Exception as e:
            print(f"❌ TTS synthesis failed: {type(e).__name__}: {e}")
            return None

    def save_wav(
        self, audio_bytes: bytes, text: str, emotion: str | None = None
    ) -> Path:
        """Save WAV audio to file."""
        self.chunk_count += 1
        emotion_tag = f"_{emotion}" if emotion else ""
        filename = f"{self.session_id}_chunk{self.chunk_count:03d}{emotion_tag}.wav"
        filepath = self.output_dir / filename

        with open(filepath, "wb") as f:
            f.write(audio_bytes)

        return filepath

    async def run_streaming_session(self, message: str):
        """Run a complete streaming session with real-time TTS."""
        print(f"\n{'='*70}")
        print("🎯 Starting Real-time TTS Streaming Demo")
        print(f"{'='*70}\n")
        print(f"📝 User message: {message}")

        # Prepare images if any
        prepared_images = []
        if self.images:
            print(f"\n🖼️  Preparing {len(self.images)} image(s)...")
            prepared_images = self._prepare_images()
            print(f"   {len(prepared_images)} image(s) ready\n")
        else:
            print("")

        tts_chunks_received = []
        stream_tokens_received = []

        try:
            async with websockets.connect(
                self.websocket_url,
                ping_interval=20,  # Send ping every 20 seconds
                ping_timeout=10,  # Wait 10 seconds for pong
                close_timeout=5,  # Wait 5 seconds when closing
            ) as websocket:
                print(f"✓ Connected to {self.websocket_url}\n")

                # Step 1: Authorize
                await self.send_json(
                    websocket, {"type": "authorize", "token": self.token}
                )

                authorized = False

                # Step 2: Listen for events
                while True:
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    except asyncio.TimeoutError:
                        print("⚠️  No message received for 60 seconds, continuing...")
                        continue

                    data = json.loads(raw)
                    event_type = data.get("type")

                    # Handle ping/pong
                    if event_type == "ping":
                        await self.send_json(websocket, {"type": "pong"})
                        continue

                    # Handle authorization
                    if event_type == "authorize_success" and not authorized:
                        authorized = True
                        connection_id = data.get("connection_id")
                        print(f"✓ Authorized (connection: {connection_id})\n")
                        print("📤 Sending chat message...", end="")
                        if prepared_images:
                            print(f" (with {len(prepared_images)} image(s))")
                        else:
                            print("")
                        print("")

                        chat_payload = {
                            "type": "chat_message",
                            "content": message,
                            "session_id": "c157b220-47c0-4c48-a878-382ba6448cd6",
                            "agent_id": "yuri",
                            "user_id": "nanami",
                        }

                        # Include images if provided
                        if prepared_images:
                            chat_payload["images"] = prepared_images

                        await self.send_json(websocket, chat_payload)
                        continue

                    # Track stream tokens (to show agent is still streaming)
                    if event_type == "stream_token":
                        token = data.get("chunk", "")
                        stream_tokens_received.append(token)
                        print(f"🔤 Token: {token}", end="", flush=True)
                        continue

                    if event_type == "stream_start":
                        print("\n" + "─" * 70)
                        print("🚀 Agent stream started")
                        print("─" * 70)
                        continue

                    # ⭐ THIS IS THE KEY EVENT: tts_ready_chunk
                    if event_type == "tts_ready_chunk":
                        chunk_text = data.get("chunk", "")
                        emotion = data.get("emotion")

                        print("\n" + "─" * 70)
                        print("🎤 TTS CHUNK RECEIVED (real-time!)")
                        print("─" * 70)
                        print(f"📝 Text: {chunk_text}")
                        if emotion:
                            print(f"😊 Emotion: {emotion}")

                        # Save the chunk info
                        tts_chunks_received.append(
                            {"text": chunk_text, "emotion": emotion}
                        )

                        # Synthesize speech via TTS API
                        print("🔊 Synthesizing speech...")
                        audio_bytes = await self.synthesize_tts(chunk_text, emotion)

                        if audio_bytes:
                            # Save to WAV file
                            filepath = self.save_wav(audio_bytes, chunk_text, emotion)
                            size_kb = len(audio_bytes) / 1024
                            print(f"💾 Saved: {filepath.name} ({size_kb:.1f} KB)")
                        else:
                            print("❌ TTS synthesis failed")

                        print("─" * 70 + "\n")
                        continue

                    if event_type == "stream_end":
                        print("\n" + "─" * 70)
                        print("✅ Agent stream completed")
                        print("─" * 70)
                        break

                    if event_type == "error":
                        error = data.get("error", "Unknown error")
                        print(f"\n❌ Error: {error}")
                        break

        except websockets.exceptions.ConnectionClosed as e:
            print(f"\n⚠️  WebSocket closed: {e.reason if hasattr(e, 'reason') else e}")
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n❌ Connection error: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()

        # Print summary
        print(f"\n{'='*70}")
        print("📊 Session Summary")
        print(f"{'='*70}")
        print(f"Stream tokens received: {len(stream_tokens_received)}")
        print(f"TTS chunks received: {len(tts_chunks_received)}")
        print(f"WAV files saved: {self.chunk_count}")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"\n{'='*70}")
        print("✅ Demo Complete!")
        print(f"{'='*70}\n")

        # Show TTS chunks details
        if tts_chunks_received:
            print("📝 TTS Chunks Details:")
            for i, chunk in enumerate(tts_chunks_received, 1):
                emotion_str = f" ({chunk['emotion']})" if chunk["emotion"] else ""
                print(f"  {i}. {chunk['text'][:60]}...{emotion_str}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Real-time TTS Streaming Demo with Image Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Basic usage with default settings (ナツメ voice)
  python examples/realtime_tts_streaming_demo.py

  # Custom message
  python examples/realtime_tts_streaming_demo.py --message "Tell me a short story"

  # With a single image URL
  python examples/realtime_tts_streaming_demo.py \\
    --message "What do you see in this image?" \\
    --image "https://example.com/image.jpg"

  # With a local image file
  python examples/realtime_tts_streaming_demo.py \\
    --message "Describe this picture" \\
    --image "./my_photo.png"

  # With multiple images
  python examples/realtime_tts_streaming_demo.py \\
    --message "Compare these images" \\
    --image "./image1.png" \\
    --image "https://example.com/image2.jpg"

  # Custom reference voice
  python examples/realtime_tts_streaming_demo.py --reference-id "ナツメ"

  # Custom output directory
  python examples/realtime_tts_streaming_demo.py --output ./my_tts_output

  # Custom API endpoints
  python examples/realtime_tts_streaming_demo.py \\
    --ws-url ws://localhost:8000/v1/chat/stream \\
    --tts-url http://localhost:8000/v1/tts/synthesize
        """,
    )
    parser.add_argument(
        "--message",
        default="Hello! Can you tell me about real-time TTS streaming?",
        help="Chat message to send to the agent",
    )
    parser.add_argument(
        "--image",
        action="append",
        dest="images",
        default=None,
        help="Image to include (URL or local file path). Can be specified multiple times.",
    )
    parser.add_argument(
        "--ws-url",
        default="ws://localhost:5500/v1/chat/stream",
        help="WebSocket endpoint URL",
    )
    parser.add_argument(
        "--tts-url",
        default="http://localhost:5500/v1/tts/synthesize",
        help="TTS API endpoint URL",
    )
    parser.add_argument(
        "--output",
        default="./tts_output",
        help="Output directory for WAV files",
    )
    parser.add_argument(
        "--token",
        default="demo-token",
        help="Authorization token",
    )
    parser.add_argument(
        "--reference-id",
        default="ナツメ",
        help="Reference voice ID for TTS (default: ナツメ)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    demo = RealtimeTTSDemo(
        websocket_url=args.ws_url,
        tts_url=args.tts_url,
        output_dir=args.output,
        token=args.token,
        reference_id=args.reference_id,
        images=args.images,
    )

    await demo.run_streaming_session(args.message)


if __name__ == "__main__":
    asyncio.run(main())
