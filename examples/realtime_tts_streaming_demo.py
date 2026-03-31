"""
Real-time TTS Streaming Demo

This example demonstrates the complete TTS streaming pipeline:
1. Connect to WebSocket API
2. Send a chat message (optionally with images)
3. Receive streaming tokens from the agent
4. Receive TTS chunks as sentences are completed (real-time)
5. Print each TTS chunk
6. Save TTS audio to files

Expected behavior:
- TTS chunks arrive WHILE the agent is still streaming (not after)
- Each complete sentence triggers a TTS chunk immediately
- Audio files are saved incrementally as they arrive
- Images can be provided as file paths or URLs
"""

import argparse
import asyncio
import base64
import io
import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any

import websockets
from PIL import Image

# Max binary image size before resizing (4MB → ~5.3MB base64, well under server limit)
_MAX_IMAGE_BYTES = 4 * 1024 * 1024


class RealtimeTTSDemo:
    """Demo client for real-time TTS streaming with optional image support."""

    def __init__(
        self,
        websocket_url: str = "ws://localhost:5500/v1/chat/stream",
        output_dir: str = "./tts_output",
        token: str = "demo-token",
        reference_id: str = "ナツメ",
        persona_id: str = "yuri",
        agent_id: str = "agent-001",
        user_id: str = "user-001",
        session_id: str | None = None,
        images: list[str] | None = None,
    ):
        self.websocket_url = websocket_url
        self.output_dir = Path(output_dir)
        self.token = token
        self.reference_id = reference_id
        self.persona_id = persona_id
        self.agent_id = agent_id
        self.user_id = user_id
        self.chat_session_id = session_id  # None = new session
        self.images = images or []
        self.chunk_count = 0
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {self.output_dir.absolute()}")
        print(f"🎙️  Reference voice: {self.reference_id}")
        print(f"🎭  Persona: {self.persona_id}")
        print(f"👤  User: {self.user_id} / Agent: {self.agent_id}")
        if self.chat_session_id:
            print(f"💬  Session: {self.chat_session_id}")
        else:
            print("💬  Session: new (will be assigned by server)")
        if self.images:
            print(f"🖼️  Images to include: {len(self.images)}")

    def _resize_to_limit(self, image_bytes: bytes) -> tuple[bytes, str]:
        """Resize image bytes to fit within _MAX_IMAGE_BYTES using Pillow.

        Returns:
            Tuple of (resized_bytes, mime_type). Output is always JPEG.
        """
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        scale = 1.0
        while True:
            if scale < 1.0:
                new_w = max(1, int(img.width * scale))
                new_h = max(1, int(img.height * scale))
                candidate = img.resize((new_w, new_h), Image.LANCZOS)
            else:
                candidate = img

            buf = io.BytesIO()
            candidate.save(buf, format="JPEG", quality=85, optimize=True)
            result = buf.getvalue()

            if len(result) <= _MAX_IMAGE_BYTES or scale < 0.1:
                return result, "image/jpeg"

            scale *= 0.75

    def _load_image_as_base64(self, image_path: str) -> str | None:
        """
        Load an image file and convert to base64 data URL.
        Automatically resizes if the file exceeds _MAX_IMAGE_BYTES.

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

            with open(path, "rb") as f:
                image_bytes = f.read()

            original_mb = len(image_bytes) / 1024 / 1024
            if len(image_bytes) > _MAX_IMAGE_BYTES:
                print(
                    f"  📐 Resizing {image_path} ({original_mb:.1f}MB → target <{_MAX_IMAGE_BYTES // 1024 // 1024}MB)..."
                )
                image_bytes, mime_type = self._resize_to_limit(image_bytes)
                print(f"     → {len(image_bytes) / 1024 / 1024:.1f}MB after resize")
            else:
                mime_type, _ = mimetypes.guess_type(str(path))
                if not mime_type or not mime_type.startswith("image/"):
                    mime_type = "image/png"

            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"

        except Exception as e:
            print(f"❌ Failed to load image {image_path}: {e}")
            return None

    def _prepare_images(self) -> list[dict]:
        """
        Prepare images for the chat message.

        Handles both:
        - URLs (http://, https://) - passed through as-is
        - Local file paths - converted to base64 data URLs

        Returns:
            List of image objects in OpenAI format
        """
        prepared = []
        for img in self.images:
            url = None
            if img.startswith(("http://", "https://", "data:")):
                # Already a URL or data URL, use as-is
                url = img
                print(
                    f"  🌐 Using URL: {img[:80]}..."
                    if len(img) > 80
                    else f"  🌐 Using URL: {img}"
                )
            else:
                # Assume it's a local file path
                url = self._load_image_as_base64(img)
                if url:
                    print(f"  📄 Loaded file: {img}")

            if url:
                prepared.append(
                    {"type": "image_url", "image_url": {"url": url, "detail": "auto"}}
                )
        return prepared

    async def send_json(self, websocket: Any, payload: dict):
        """Send JSON message to websocket."""
        message = json.dumps(payload)
        await websocket.send(message)
        print(f">> {payload['type']}")

    def save_audio(
        self, audio_bytes: bytes, sequence: int, emotion: str | None = None
    ) -> Path:
        """Save audio to file."""
        self.chunk_count += 1
        emotion_tag = f"_{emotion}" if emotion else ""
        filename = f"{self.session_id}_seq{sequence:03d}{emotion_tag}.wav"
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

                    # Handle authorization errors
                    if event_type == "authorize_error":
                        error = data.get("error", "Unknown authorization error")
                        print(f"\n❌ Authorization failed: {error}")
                        break

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
                            "session_id": self.chat_session_id,
                            "agent_id": self.agent_id,
                            "user_id": self.user_id,
                            "persona_id": self.persona_id,
                            "tts_enabled": True,
                            "reference_id": self.reference_id,
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
                        turn_id = data.get("turn_id", "")
                        srv_session_id = data.get("session_id", "")
                        print("\n" + "─" * 70)
                        print(f"🚀 Agent stream started (turn={turn_id}, session={srv_session_id})")
                        print("─" * 70)
                        continue

                    if event_type == "tool_call":
                        tool_name = data.get("tool_name", "")
                        args = data.get("args", "")
                        print(f"\n🔧 Tool call: {tool_name}({args})")
                        continue

                    if event_type == "tool_result":
                        result = data.get("result", "")
                        print(f"\n📋 Tool result: {result[:120]}{'...' if len(result) > 120 else ''}")
                        continue

                    # ⭐ THIS IS THE KEY EVENT: tts_chunk
                    if event_type == "tts_chunk":
                        sequence = data.get("sequence", 0)
                        chunk_text = data.get("text", "")
                        emotion = data.get("emotion")
                        keyframes = data.get("keyframes", [])
                        audio_base64 = data.get("audio_base64")

                        print("\n" + "─" * 70)
                        print(f"🎤 TTS CHUNK [{sequence}] RECEIVED (real-time!)")
                        print("─" * 70)
                        print(f"📝 Text: {chunk_text}")
                        if emotion:
                            print(f"😊 Emotion: {emotion}")
                        if keyframes:
                            print(f"🎭 Keyframes: {keyframes}")

                        # Save the chunk info
                        tts_chunks_received.append(
                            {
                                "sequence": sequence,
                                "text": chunk_text,
                                "emotion": emotion,
                            }
                        )

                        if audio_base64:
                            audio_bytes = base64.b64decode(audio_base64)
                            # Save to file
                            filepath = self.save_audio(audio_bytes, sequence, emotion)
                            size_kb = len(audio_bytes) / 1024
                            print(f"💾 Saved: {filepath.name} ({size_kb:.1f} KB)")
                        else:
                            print(
                                "⚠️ No audio data in chunk (tts_enabled=false or failed)"
                            )

                        print("─" * 70 + "\n")
                        continue

                    if event_type == "stream_end":
                        turn_id = data.get("turn_id", "")
                        srv_session_id = data.get("session_id", "")
                        final_content = data.get("content", "")
                        print("\n" + "─" * 70)
                        print(f"✅ Agent stream completed (turn={turn_id}, session={srv_session_id})")
                        if final_content:
                            print(f"📄 Full response: {final_content[:200]}{'...' if len(final_content) > 200 else ''}")
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
        print(f"Audio files saved: {self.chunk_count}")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"\n{'='*70}")
        print("✅ Demo Complete!")
        print(f"{'='*70}\n")

        # Show TTS chunks details
        if tts_chunks_received:
            print("📝 TTS Chunks Details:")
            for chunk in tts_chunks_received:
                emotion_str = f" ({chunk['emotion']})" if chunk["emotion"] else ""
                print(f"  {chunk['sequence']}. {chunk['text'][:60]}...{emotion_str}")


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
    --ws-url ws://localhost:8000/v1/chat/stream
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
        "--output",
        default="./tts_output",
        help="Output directory for audio files",
    )
    parser.add_argument(
        "--token",
        default="demo-token",
        help="Authorization token",
    )
    parser.add_argument(
        "--reference-id",
        default="七海",
        help="Reference voice ID for TTS (default: 七海)",
    )
    parser.add_argument(
        "--persona-id",
        default="yuri",
        help="Persona ID — must match a key in yaml_files/personas.yml (default: yuri)",
    )
    parser.add_argument(
        "--agent-id",
        default="agent-001",
        help="Persistent agent identifier (default: agent-001)",
    )
    parser.add_argument(
        "--user-id",
        default="user-001",
        help="Persistent user/client identifier (default: user-001)",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Existing session UUID to continue (default: None = new session)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    demo = RealtimeTTSDemo(
        websocket_url=args.ws_url,
        output_dir=args.output,
        token=args.token,
        reference_id=args.reference_id,
        persona_id=args.persona_id,
        agent_id=args.agent_id,
        user_id=args.user_id,
        session_id=args.session_id,
        images=args.images,
    )

    await demo.run_streaming_session(args.message)


if __name__ == "__main__":
    asyncio.run(main())
