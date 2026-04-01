import asyncio
import base64
import contextlib
from concurrent.futures import Future as ConcurrentFuture
from typing import Annotated, Literal

import ormsgpack
import requests  # type: ignore
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, conint, model_validator

from src.services.tts_service.service import TTSService


class ServeReferenceAudio(BaseModel):
    audio: bytes
    text: str

    @model_validator(mode="before")
    def decode_audio(cls, values):
        audio = values.get("audio")
        if isinstance(audio, str):
            with contextlib.suppress(Exception):
                values["audio"] = base64.b64decode(audio)
        return values

    def __repr__(self) -> str:
        return f"ServeReferenceAudio(text={self.text!r}, audio_size={len(self.audio)})"


class ServeTTSRequest(BaseModel):
    text: str
    chunk_length: Annotated[int, conint(ge=100, le=300, strict=True)] = 200
    # Audio format
    format: Literal["wav", "pcm", "mp3"] = "mp3"
    # References audios for in-context learning
    references: list[ServeReferenceAudio] = []
    # Reference id
    reference_id: str | None = None
    seed: int | None = 1004
    use_memory_cache: Literal["on", "off"] = "off"
    # Normalize text for en & zh, this increase stability for numbers
    normalize: bool = True
    # not usually used below
    streaming: bool = False
    max_new_tokens: int = 1024
    top_p: Annotated[float, Field(ge=0.1, le=1.0, strict=True)] = 0.8
    repetition_penalty: Annotated[float, Field(ge=0.9, le=2.0, strict=True)] = 1.1
    temperature: Annotated[float, Field(ge=0.1, le=1.0, strict=True)] = 0.8

    # AIDEV-NOTE: Migrated from class Config to ConfigDict for Pydantic v2 compatibility
    model_config = ConfigDict(arbitrary_types_allowed=True)


class FishSpeechTTS(TTSService):
    """
    외부 TTS API와 통신하여 텍스트로부터 음성을 생성하는 서비스입니다.
    텍스트 처리부터 API 요청까지 모든 과정을 캡슐화합니다.
    직렬 큐 워커를 통해 동시 요청을 순차적으로 처리합니다.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        api_key: str | None = None,
        seed: int | None = None,
        streaming: bool = False,
        use_memory_cache: Literal["on", "off"] = "off",
        chunk_length: int = 200,
        max_new_tokens: int = 1024,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        temperature: float = 0.7,
    ):
        """
        Initialize FishTTS Engine with all synthesis parameters.

        Args:
            base_url: TTS API URL
            api_key: Authentication token
            reference_audio_paths: string of audio paths (use <sep> for multiple)
            reference_texts: string of matching reference texts (use <sep> for multiple)
            seed: Seed for deterministic generation
            streaming: Whether to stream audio output
            use_memory_cache: Whether to cache reference encodings
            chunk_length: Length of each synthesis chunk
            max_new_tokens: Max new tokens to generate
            top_p: Top-p sampling value
            repetition_penalty: Penalty for repeating phrases
            temperature: Sampling temperature
        """

        self.api_key = api_key
        self.base_url = base_url

        self.seed = seed
        self.streaming = streaming
        self.use_memory_cache = use_memory_cache
        self.chunk_length = chunk_length
        self.max_new_tokens = max_new_tokens
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.temperature = temperature

        # Serial queue worker — initialized by start_worker() in async lifespan
        self._queue: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._worker_task: asyncio.Task | None = None

        logger.info(f"FishTTS initialized at {self.base_url}")

    async def start_worker(self) -> None:
        """Start the serial TTS queue worker. Must be called from async context (lifespan)."""
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._serial_worker())
        logger.info("FishSpeechTTS serial queue worker started")

    async def stop_worker(self) -> None:
        """Stop the serial queue worker."""
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        self._queue = None
        self._loop = None

    async def _serial_worker(self) -> None:
        """Process TTS HTTP requests one at a time from the queue."""
        while True:
            payload, loop_future = await self._queue.get()
            try:
                result = await asyncio.to_thread(self._request_tts_stream, payload)
                if not loop_future.done():
                    loop_future.set_result(result)
            except Exception as e:
                if not loop_future.done():
                    loop_future.set_exception(e)
            finally:
                self._queue.task_done()

    def _request_tts_stream(self, request_payload: ServeTTSRequest) -> bytes | None:
        """
        [내부 메서드] TTS 요청을 보내고 오디오 데이터를 바이트로 반환합니다.

        Args:
            request_payload: API에 전송할 Pydantic 요청 모델

        Returns:
            성공 시 오디오 바이트 데이터, 실패 시 None
        """
        try:
            response = requests.post(
                self.base_url,
                data=ormsgpack.packb(
                    request_payload, option=ormsgpack.OPT_SERIALIZE_PYDANTIC
                ),
                stream=self.streaming,
                headers={
                    "authorization": f"Bearer {self.api_key or ''}",
                    "content-type": "application/msgpack",
                },
                timeout=120,
            )
            response.raise_for_status()
            return bytes(response.content)
        except requests.exceptions.RequestException as e:
            logger.error(f"TTS API 요청 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"TTS 처리 중 예상치 못한 오류: {e}")
            return None

    def generate_speech(
        self,
        text: str,
        reference_id: str | None = None,
        output_format: Literal["bytes", "base64", "file"] = "bytes",
        output_filename: str | None = "output.wav",
        audio_format: Literal["wav", "mp3"] = "mp3",
    ) -> bytes | str | bool | None:
        """
        [메인 메서드] 원본 텍스트를 받아 음성을 생성하고 지정된 포맷으로 반환합니다.
        큐 워커가 실행 중이면 직렬 처리, 아니면 직접 호출합니다.

        Args:
            raw_text: LLM으로부터 받은 원본 텍스트
            reference_id: 사용할 음성 레퍼런스 ID
            output_format: 반환할 오디오 데이터 형식 ('bytes', 'base64', 'file')
            output_filename: 'file' 포맷일 경우 저장할 파일명
            audio_format: 오디오 코덱 형식 ('wav' 또는 'mp3')

        Returns:
            - "bytes": 오디오 데이터 (bytes)
            - "base64": Base64 인코딩된 문자열 (str)
            - "file": 저장 성공 여부 (bool)
            - 처리할 텍스트가 없거나 실패 시 None
        """

        # 1. TTS로 처리할 텍스트가 있는지 확인
        tts_text = text.strip()
        if not tts_text:
            return None

        # 3. API 요청 페이로드 생성
        request_payload = ServeTTSRequest(
            text=tts_text, reference_id=reference_id, format=audio_format
        )

        # 4. 큐 워커가 활성화된 경우 직렬 처리, 아니면 직접 호출
        if (
            self._loop is not None
            and self._queue is not None
            and self._loop.is_running()
        ):
            audio_bytes = self._enqueue_and_wait(request_payload)
        else:
            audio_bytes = self._request_tts_stream(request_payload)

        if not audio_bytes:
            return None

        # 5. 요청된 포맷에 맞춰 결과 반환
        if output_format == "base64":
            return base64.b64encode(audio_bytes).decode("utf-8")
        elif output_format == "file":
            try:
                with open(output_filename, "wb") as f:
                    f.write(audio_bytes)
                return True
            except Exception:
                return False
        else:  # "bytes"가 기본값
            return audio_bytes

    def _enqueue_and_wait(self, request_payload: ServeTTSRequest) -> bytes | None:
        """Submit payload to async queue from sync thread context and wait for result."""
        loop = self._loop
        queue = self._queue

        async def _submit() -> bytes | None:
            loop_future: asyncio.Future = loop.create_future()
            await queue.put((request_payload, loop_future))
            return await loop_future

        try:
            concurrent_future: ConcurrentFuture = asyncio.run_coroutine_threadsafe(
                _submit(), loop
            )
            return concurrent_future.result(timeout=120)
        except Exception as e:
            logger.error(f"TTS 큐 처리 중 오류: {e}")
            return None

    def list_voices(self) -> list[str]:
        """FishSpeech does not manage reference voice directories."""
        return []

    def is_healthy(self) -> tuple[bool, str]:
        """Check Fish Speech TTS health by attempting a minimal synthesis."""
        try:
            # Try a simple synthesis as a health check
            result = self.generate_speech(text="test", output_format="bytes")
            if result:
                return True, "Fish Speech TTS is healthy"
            else:
                return False, "Fish Speech TTS returned empty result"
        except Exception as e:
            return False, f"Fish Speech TTS health check failed: {e!s}"


# --- 사용 예제 ---
if __name__ == "__main__":
    # TTS 서비스 URL (실제 URL로 변경 필요)
    TTS_API_URL = "http://192.168.41:8080/v1/tts"

    # 1. 서비스 인스턴스 생성
    tts_service = FishSpeechTTS(base_url=TTS_API_URL)

    # 2. LLM에서 받은 것과 유사한 원본 텍스트
    llm_output_text = "(delighted) That's wonderful news! I'm so happy for you!"

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
        reference_id="ナツメ",
    )

    if file_audio:
        print("성공! 파일로 저장되었습니다: output.wav")
    else:
        print("실패.")
