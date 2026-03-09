import base64
import mimetypes
from pathlib import Path
from typing import Literal, Optional

import httpx
from loguru import logger

from src.services.tts_service.service import TTSService


class VLLMOmniTTSService(TTSService):
    """
    vLLM 기반 Qwen Omni TTS API와 통신하여 텍스트로부터 음성을 생성하는 서비스입니다.
    OpenAI-compatible /v1/audio/speech 엔드포인트를 사용합니다.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5517",
        api_key: str = "token-abc123",
        model: str = "chat_model",
        task_type: str = "Base",
        response_format: Literal["mp3", "wav"] = "mp3",
        ref_audio_dir: str = "./resources/references_voices",
        timeout: float = 300.0,
    ):
        """
        Initialize VLLMOmni TTS Engine.

        Args:
            base_url: vLLM TTS API base URL (without /v1/audio/speech)
            api_key: Bearer token for authentication
            model: Model name to use for synthesis
            task_type: Task type for the TTS request (e.g. "Base")
            response_format: Audio output format ('mp3' or 'wav')
            ref_audio_dir: Directory containing reference voice subdirectories
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.task_type = task_type
        self.response_format = response_format
        self.ref_audio_dir = Path(ref_audio_dir)
        self.timeout = timeout

        # Cache for loaded reference audio/text to avoid repeated disk I/O
        self._ref_cache: dict[str, tuple[str, str]] = {}

        logger.info(f"VLLMOmniTTS initialized at {self.base_url}")

    def _file_to_data_url(self, file_path: Path) -> str:
        """Convert an audio file to a base64 data URL string."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "audio/wav"

        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{encoded}"

    def _load_reference(self, reference_id: str) -> tuple[str, str]:
        """
        Load reference audio and text for the given voice ID.

        Looks for:
          - {ref_audio_dir}/{reference_id}/merged_audio.mp3
          - {ref_audio_dir}/{reference_id}/combined.lab

        Args:
            reference_id: Name of the reference voice directory

        Returns:
            Tuple of (ref_audio_data_url, ref_text)

        Raises:
            FileNotFoundError: If reference files are missing
        """
        if reference_id in self._ref_cache:
            return self._ref_cache[reference_id]

        ref_dir = self.ref_audio_dir / reference_id
        audio_path = ref_dir / "merged_audio.mp3"
        text_path = ref_dir / "combined.lab"

        if not audio_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {audio_path}")
        if not text_path.exists():
            raise FileNotFoundError(f"Reference text not found: {text_path}")

        ref_audio_data = self._file_to_data_url(audio_path)
        with open(text_path, "r", encoding="utf-8") as f:
            ref_text = f.read().strip().replace("\n", "")

        self._ref_cache[reference_id] = (ref_audio_data, ref_text)
        return self._ref_cache[reference_id]

    def _request_tts(
        self,
        text: str,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        audio_format: Literal["wav", "mp3"] = "mp3",
    ) -> Optional[bytes]:
        """
        Send a TTS request to the vLLM Omni API and return raw audio bytes.

        Args:
            text: Text to synthesize
            ref_audio: Base64 data URL of reference audio
            ref_text: Reference transcript text
            audio_format: Desired audio output format

        Returns:
            Audio bytes on success, None on failure
        """
        url = f"{self.base_url}/v1/audio/speech"

        payload: dict = {
            "model": self.model,
            "task_type": self.task_type,
            "input": text,
            "response_format": audio_format,
        }

        if ref_audio is not None:
            payload["ref_audio"] = ref_audio
        if ref_text is not None:
            payload["ref_text"] = ref_text

        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return bytes(response.content)
        except httpx.HTTPStatusError as e:
            logger.error(
                f"TTS API HTTP error: {e.response.status_code} - {e.response.text[:200]}"
            )
            return None
        except httpx.RequestError as e:
            logger.error(f"TTS API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"TTS unexpected error: {e}")
            return None

    def generate_speech(
        self,
        text: str,
        reference_id: Optional[str] = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: Optional[str] = "output.mp3",
        audio_format: Literal["wav", "mp3"] = "mp3",
    ) -> Optional[bytes | str | bool]:
        """
        Generate speech from text using the vLLM Omni TTS API.

        Args:
            text: The text to synthesize
            reference_id: Reference voice directory name (e.g. "ナツメ")
            output_format: Output format ('bytes', 'base64', 'file')
            output_filename: Filename when output_format is 'file'
            audio_format: Audio codec format ('wav' or 'mp3')

        Returns:
            - "bytes": Raw audio bytes
            - "base64": Base64-encoded string
            - "file": True on success, False on failure
            - None if text is empty or synthesis fails
        """
        tts_text = text.strip()
        if not tts_text:
            return None

        # Load reference voice if specified
        ref_audio: Optional[str] = None
        ref_text: Optional[str] = None
        if reference_id:
            try:
                ref_audio, ref_text = self._load_reference(reference_id)
            except FileNotFoundError as e:
                logger.error(f"Reference voice load failed: {e}")
                return None

        # Call the API
        audio_bytes = self._request_tts(
            text=tts_text,
            ref_audio=ref_audio,
            ref_text=ref_text,
            audio_format=audio_format,
        )

        if not audio_bytes:
            return None

        # Return in the requested format
        if output_format == "base64":
            return base64.b64encode(audio_bytes).decode("utf-8")
        elif output_format == "file":
            try:
                with open(output_filename, "wb") as f:
                    f.write(audio_bytes)
                return True
            except Exception as e:
                logger.error(f"File save error: {e}")
                return False
        else:
            return audio_bytes

    def is_healthy(self) -> tuple[bool, str]:
        """Check if the vLLM Omni TTS API is reachable."""
        try:
            response = httpx.get(
                f"{self.base_url}/health",
                timeout=10.0,
            )
            if response.status_code == 200:
                return True, "VLLMOmni TTS is healthy"
            return False, f"VLLMOmni TTS health check returned {response.status_code}"
        except Exception as e:
            return False, f"VLLMOmni TTS health check failed: {str(e)}"


# --- 사용 예제 ---
if __name__ == "__main__":
    # TTS 서비스 URL (실제 URL로 변경 필요)
    TTS_API_URL = "http://192.168.0.41:5517"

    # 1. 서비스 인스턴스 생성
    tts_service = VLLMOmniTTSService(
        base_url=TTS_API_URL,
        api_key="token-abc123",
        model="chat_model",
    )

    # 2. LLM에서 받은 것과 유사한 원본 텍스트
    llm_output_text = "That's wonderful news! I'm so happy for you!"

    # 3. 서비스의 메인 메서드 하나만 호출하여 오디오 데이터 받기
    print("--- 'bytes' 포맷으로 오디오 생성 시도 ---")
    audio_data = tts_service.generate_speech(
        text=llm_output_text,
        reference_id="ナツメ",
        output_format="bytes",
    )

    if audio_data and isinstance(audio_data, bytes):
        print(f"성공! 오디오 데이터 수신 (크기: {len(audio_data)} bytes)")
    else:
        print("실패.")

    print("\n--- 'file' 포맷으로 오디오 생성 시도 ---")
    file_audio = tts_service.generate_speech(
        text=llm_output_text,
        output_format="file",
        output_filename="output.wav",
        audio_format="wav",
        reference_id="ナツメ",
    )

    if file_audio:
        print("성공! 파일로 저장되었습니다: output.wav")
    else:
        print("실패.")

    print("\n--- 'file' 포맷으로 오디오 생성 시도 ---")
    file_audio = tts_service.generate_speech(
        text=llm_output_text,
        output_format="file",
        output_filename="output.mp3",
        audio_format="mp3",
        reference_id="ナツメ",
    )

    if file_audio:
        print("성공! 파일로 저장되었습니다: output.mp3")
    else:
        print("실패.")

    print(tts_service._ref_cache)
