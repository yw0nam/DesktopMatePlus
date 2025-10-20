import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage


class LLMFactory:
    @staticmethod
    def get_llm_service(service_type: str, **kwargs) -> BaseChatModel:
        """
        Factory method to create LLM service instances.

        Args:
            service_type: Type of LLM service to create
            **kwargs: Additional configuration parameters

        Returns:
            LLMService: Instance of the requested LLM service

        Raises:
            ValueError: If service_type is unknown
        """
        if service_type == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                temperature=kwargs.get("temperature", 0.7),
                top_p=kwargs.get("top_p", 0.9),
                openai_api_key=kwargs.get("openai_api_key"),
                openai_api_base=kwargs.get("openai_api_base"),
                model_name=kwargs.get("model_name"),
            )
        else:
            raise ValueError(f"Unknown LLM service type: {service_type}")


if __name__ == "__main__":
    load_dotenv()
    # 1. 서비스 인스턴스 생성
    chat_model = LLMFactory.get_llm_service(
        "openai",
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("LLM_MODEL_NAME"),
    )
    # 2. Load Image and prepare prompt

    history = [HumanMessage(content="Hello world!")]
    # 3. 서비스의 메인메서드 하나 호출하여 이미지 description 받기
    output = chat_model.invoke(input=history)

    if output:
        print(f"성공!: {output}")
    else:
        print("실패.")
