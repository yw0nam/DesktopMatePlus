import os

from dotenv import load_dotenv

from src.services.vlm_service.service import VLMService


class VLMFactory:
    @staticmethod
    def get_vlm_service(service_type: str, **kwargs) -> VLMService:
        """
        Factory method to create VLM service instances.

        Args:
            service_type: Type of VLM service to create
            **kwargs: Additional configuration parameters

        Returns:
            VLMService: Instance of the requested VLM service

        Raises:
            ValueError: If service_type is unknown
        """
        if service_type == "openai_chat_agent":
            from src.services.vlm_service.openai_compatible import OpenAIService

            kwargs["openai_api_key"] = os.getenv("VLM_API_KEY")

            return OpenAIService(
                temperature=kwargs.get("temperature", 0.7),
                top_p=kwargs.get("top_p", 0.9),
                openai_api_key=kwargs.get("openai_api_key"),
                openai_api_base=kwargs.get("openai_api_base"),
                model_name=kwargs.get("model_name"),
            )
        else:
            raise ValueError(f"Unknown VLM service type: {service_type}")


# Example usage:
# vlm_service = VLMFactory.get_vlm_service("openai", openai_api_key="your_api_key", openai_api_base="your_api_base", model_name="your_model_name")
# vlm_service.generate_response(image="your_image", prompt="Describe this image")
if __name__ == "__main__":
    load_dotenv()
    # 1. 서비스 인스턴스 생성
    vlm_service = VLMFactory.get_vlm_service(
        "openai",
        openai_api_key=os.getenv("VLM_API_KEY"),
        openai_api_base=os.getenv("VLM_BASE_URL"),
        model_name=os.getenv("VLM_MODEL_NAME"),
    )
    # 2. Load Image and prepare prompt

    prompt = "Describe this image"
    image = "https://external-preview.redd.it/shiki-natsume-v0-wBgSzBHXBZrzjI8f0mIQ_40-pe6069ikT9xnoNn2liA.jpg?auto=webp&s=3fdbd0ceb69cab6c2efc6dd68559ca7fa8a7d191"
    # 3. 서비스의 메인메서드 하나 호출하여 이미지 description 받기
    description = vlm_service.generate_response(image=image, prompt=prompt)

    if description:
        print(f"성공! 이미지 설명 수신: {description}")
    else:
        print("실패.")
