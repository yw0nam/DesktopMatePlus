"""Simple websocket client for local testing."""

import argparse
import asyncio
import json
from typing import Any, Dict

import websockets


async def send_authorize(websocket: Any, token: str):
    payload = {"type": "authorize", "token": token}
    message = json.dumps(payload)
    print(f">> {message}")
    await websocket.send(message)


async def send_chat_message(
    websocket: Any,
    content: str,
    metadata: Dict[str, Any] | None,
):
    payload = {
        "type": "chat_message",
        "content": content,
    }
    if metadata:
        payload["metadata"] = metadata
    message = json.dumps(payload)
    print(f">> {message}")
    await websocket.send(message)


async def run_client(url: str, token: str, message: str, metadata: Dict[str, Any] | None):
    try:
        async with websockets.connect(url) as websocket:
            print(f"Connected to {url}")
            await send_authorize(websocket, token)

            authorized = False
            while True:
                raw = await websocket.recv()
                print(f"<< {raw}")
                data = json.loads(raw)
                print(f"<< parsed: {data}")

                msg_type = data.get("type")
                if msg_type == "ping":
                    pong_payload = {"type": "pong"}
                    pong_message = json.dumps(pong_payload)
                    await websocket.send(pong_message)
                    print(f">> {pong_message}")
                    continue

                if msg_type == "authorize_success" and not authorized:
                    authorized = True
                    await send_chat_message(websocket, message, metadata)
                    print(">> chat_message sent")
                    continue

                if msg_type in {"chat_response", "stream_end", "error"}:
                    # Stop after first final message for demo purposes
                    break

            print("Closing connection")
    except OSError as exc:
        raise SystemExit(f"Failed to connect to {url}: {exc}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DesktopMate+ websocket client demo")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000/v1/chat/stream",
        help="Websocket endpoint",
    )
    parser.add_argument(
        "--token",
        default="demo-token",
        help="Authorization token to send during handshake",
    )
    parser.add_argument(
        "--message",
        default="Hello from the websocket demo!",
        help="Chat message content",
    )
    parser.add_argument(
        "--metadata",
        default=None,
        help="Optional metadata JSON string to include with the chat message",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid metadata JSON: {exc}") from exc

    asyncio.run(run_client(args.url, args.token, args.message, metadata))


if __name__ == "__main__":
    main()
