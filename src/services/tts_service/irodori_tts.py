"""Irodori TTS client service (Aratako/Irodori-TTS-500M-v2).

Sends text to a running Irodori TTS server via POST /synthesize (multipart form)
and returns WAV bytes. Emoji embedded in text are passed through as-is so the
server can use them for emotion control.

Graceful degradation: any network or HTTP error logs a warning and returns None
so the caller can continue without audio.
"""

import base64
from pathlib import Path
from typing import Literal

import httpx
from loguru import logger

from src.services.tts_service.service import TTSService


class IrodoriTTSService(TTSService):
    """HTTP client for Irodori TTS POST /synthesize endpoint."""

    def __init__(
        self,
        base_url: str,
        reference_audio_path: str | None = None,
        seconds: float = 30.0,
        num_steps: int = 40,
        cfg_scale_text: float = 3.0,
        cfg_scale_speaker: float = 5.0,
        seed: int | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.reference_audio_path = reference_audio_path
        self.seconds = seconds
        self.num_steps = num_steps
        self.cfg_scale_text = cfg_scale_text
        self.cfg_scale_speaker = cfg_scale_speaker
        self.seed = seed
        self.timeout = timeout
        logger.info(f"IrodoriTTS initialized at {self.base_url}")

    def _post_synthesize(self, text: str) -> bytes | None:
        """Send POST /synthesize and return raw WAV bytes, or None on failure."""
        url = f"{self.base_url}/synthesize"
        data: dict[str, str | int | float] = {
            "text": text,
            "seconds": self.seconds,
            "num_steps": self.num_steps,
            "cfg_scale_text": self.cfg_scale_text,
            "cfg_scale_speaker": self.cfg_scale_speaker,
        }
        if self.seed is not None:
            data["seed"] = self.seed

        try:
            if self.reference_audio_path:
                with Path(self.reference_audio_path).open("rb") as ref_handle:
                    files = {
                        "reference_audio": (
                            Path(self.reference_audio_path).name,
                            ref_handle,
                            "audio/wav",
                        )
                    }
                    with httpx.Client(timeout=self.timeout) as client:
                        response = client.post(url, data=data, files=files)
                        response.raise_for_status()
                        return bytes(response.content)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, data=data)
                    response.raise_for_status()
                    return bytes(response.content)
        except httpx.HTTPStatusError as exc:
            logger.error(f"IrodoriTTS HTTP error {exc.response.status_code} from {url}")
            return None
        except httpx.RequestError as exc:
            logger.error(f"IrodoriTTS request failed: {exc}")
            return None
        except Exception as exc:
            logger.error(f"IrodoriTTS unexpected error: {exc}")
            return None

    def generate_speech(
        self,
        text: str,
        reference_id: str | None = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: str | None = "output.wav",
        audio_format: Literal["wav", "mp3"] = "wav",
    ) -> bytes | str | bool | None:
        """Generate speech from text using Irodori TTS.

        Args:
            text: Text to synthesize. May contain emoji for emotion control.
            reference_id: Ignored — ABC compatibility only. Use reference_audio_path at init.
            output_format: 'bytes' | 'base64' | 'file'
            output_filename: Destination path when output_format == 'file'.
            audio_format: Ignored — Irodori always returns WAV.

        Returns:
            bytes, base64 str, True (file saved), or None on failure/empty text.
        """
        tts_text = text.strip()
        if not tts_text:
            return None

        audio_bytes = self._post_synthesize(tts_text)
        if not audio_bytes:
            return None

        if output_format == "base64":
            return base64.b64encode(audio_bytes).decode("utf-8")
        elif output_format == "file":
            if not output_filename:
                logger.error(
                    "IrodoriTTS file save error: output_filename is required for 'file' output_format"
                )
                return False
            try:
                with open(output_filename, "wb") as f:
                    f.write(audio_bytes)
                return True
            except Exception as exc:
                logger.error(f"IrodoriTTS file save error: {exc}")
                return False
        else:
            return audio_bytes

    def list_voices(self) -> list[str]:
        """Return available voice identifiers.

        Returns the stem of reference_audio_path when set,
        otherwise ['no-reference'].
        """
        if self.reference_audio_path:
            return [Path(self.reference_audio_path).stem]
        return ["no-reference"]

    def is_healthy(self) -> tuple[bool, str]:
        """Check Irodori TTS server health via GET /health.

        Returns:
            (True, 'ok') when server responds with status=='ok',
            (False, message) otherwise.
        """
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "ok":
                return (
                    True,
                    f"IrodoriTTS is ok (pool={data.get('pool_size')}, available={data.get('available')})",
                )
            return False, f"IrodoriTTS status: {data.get('status')}"
        except Exception as exc:
            return False, f"IrodoriTTS health check failed: {exc}"
