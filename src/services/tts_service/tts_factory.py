from pathlib import Path

from loguru import logger

from src.services.tts_service.service import TTSService


class TTSFactory:
    @staticmethod
    def get_tts_engine(engine_type: str, **kwargs) -> TTSService:
        """
        Factory method to create TTS engine instances.

        Args:
            engine_type: Type of TTS engine to create
            **kwargs: Additional configuration parameters

        Returns:
            TTSService: Instance of the requested TTS engine

        Raises:
            ValueError: If engine_type is unknown
        """
        if engine_type == "vllm_omni":
            from src.configs.tts import VLLMOmniTTSConfig
            from src.services.tts_service.vllm_omni import VLLMOmniTTSService

            tts_config = VLLMOmniTTSConfig(**kwargs)
            return VLLMOmniTTSService(**tts_config.model_dump())

        elif engine_type == "irodori":
            from src.configs.tts.irodori import IrodoriTTSConfig
            from src.services.tts_service.irodori_tts import IrodoriTTSService

            tts_config = IrodoriTTSConfig(**kwargs)
            return IrodoriTTSService(**tts_config.model_dump())
        else:
            raise ValueError(f"Unknown TTS engine type: {engine_type}")


if __name__ == "__main__":
    import yaml

    _yaml_path = (
        Path(__file__).resolve().parents[3]
        / "yaml_files"
        / "services"
        / "tts_service"
        / "irodori.yml"
    )
    with open(_yaml_path, encoding="utf-8") as _f:
        _cfg = yaml.safe_load(_f)
    IRODORI_URL = _cfg["tts_config"]["configs"]["base_url"]

    tts_service = TTSFactory.get_tts_engine("irodori", base_url=IRODORI_URL)
    llm_output_text = "😊That's wonderful news! I'm so happy for you!"

    logger.info("--- 'bytes' 포맷으로 오디오 생성 시도 ---")
    audio_data = tts_service.generate_speech(
        text=llm_output_text,
        reference_id="ナツメ",
        output_format="bytes",
    )

    if audio_data and isinstance(audio_data, bytes):
        logger.info(f"성공! 오디오 데이터 수신 (크기: {len(audio_data)} bytes)")
    else:
        logger.warning("실패.")
