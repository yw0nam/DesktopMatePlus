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
            from src.services.tts_service.fish_speech import FishSpeechTTS

            return FishSpeechTTS(
                url=kwargs.get("base_url", "http://localhost:8080"),
                api_key=kwargs.get("api_key"),
                seed=kwargs.get("seed"),
                streaming=kwargs.get("streaming", False),
                use_memory_cache=kwargs.get("use_memory_cache", "off"),
                chunk_length=kwargs.get("chunk_length", 200),
                max_new_tokens=kwargs.get("max_new_tokens", 1024),
                top_p=kwargs.get("top_p", 0.7),
                repetition_penalty=kwargs.get("repetition_penalty", 1.2),
                temperature=kwargs.get("temperature", 0.7),
            )
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
