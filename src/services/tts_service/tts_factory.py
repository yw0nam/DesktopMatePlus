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
        if engine_type == "fish_local_tts":
            from src.configs.tts import FishLocalTTSConfig
            from src.services.tts_service.fish_speech import FishSpeechTTS

            tts_config = FishLocalTTSConfig(**kwargs)
            return FishSpeechTTS(**tts_config.model_dump())
        else:
            raise ValueError(f"Unknown TTS engine type: {engine_type}")


# Example usage:
# tts_engine = TTSFactory.get_tts_engine("azure", api_key="your_api_key", region="your_region", voice="your_voice")
# tts_engine.speak("Hello world")
if __name__ == "__main__":
    TTS_API_URL = "http://localhost:8080/v1/tts"

    # 1. 서비스 인스턴스 생성
    tts_service = TTSFactory.get_tts_engine(
        "fish_local_tts",
        base_url=TTS_API_URL,
    )
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
