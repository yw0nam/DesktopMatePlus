import os

from dotenv import load_dotenv

from src.services.agent_service.service import AgentService


class AgentFactory:
    @staticmethod
    def get_agent_service(service_type: str, **kwargs) -> AgentService:
        """
        Factory method to create Agent service instances.

        Args:
            service_type: Type of Agent service to create
            **kwargs: Additional configuration parameters

        Returns:
            AgentService: Instance of the requested Agent service

        Raises:
            ValueError: If service_type is unknown
        """
        if service_type == "openai_chat_agent":
            from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

            kwargs["openai_api_key"] = os.getenv("LLM_API_KEY")
            return OpenAIChatAgent(
                temperature=kwargs.get("temperature", 0.7),
                top_p=kwargs.get("top_p", 0.9),
                openai_api_key=kwargs.get("openai_api_key"),
                openai_api_base=kwargs.get("openai_api_base"),
                model_name=kwargs.get("model_name"),
                mcp_config=kwargs.get("mcp_config"),
            )
        else:
            raise ValueError(f"Unknown Agent service type: {service_type}")


# Example usage:
# agent_service = AgentFactory.get_agent_service("openai_chat_agent", openai_api_key="your_api_key", openai_api_base="your_api_base", model_name="your_model_name")
# agent_service.generate_response(image="your_image", prompt="Describe this image")
if __name__ == "__main__":
    import asyncio

    load_dotenv()
    # 1. 서비스 인스턴스 생성

    agent_service = AgentFactory.get_agent_service(
        "openai_chat_agent",
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("LLM_MODEL_NAME"),
    )

    async def main():
        return await agent_service.is_healthy()

    # 2. Load Image and prepare prompt

    # 3. 서비스의 메인메서드 하나 호출하여 이미지 description 받기
    test = asyncio.run(main())
    if test:
        print(f"성공! 에이전트 상태: {test}")
    else:
        print("실패.")
