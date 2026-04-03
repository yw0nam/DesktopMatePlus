import os
from pathlib import Path

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
            from src.configs.agent import OpenAIChatAgentConfig
            from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

            agent_config = OpenAIChatAgentConfig(**kwargs)
            return OpenAIChatAgent(**agent_config.model_dump())
        else:
            raise ValueError(f"Unknown Agent service type: {service_type}")


# Example usage:
# agent_service = AgentFactory.get_agent_service("openai_chat_agent", openai_api_key="your_api_key", openai_api_base="your_api_base", model_name="your_model_name")
# agent_service.generate_response(image="your_image", prompt="Describe this image")
if __name__ == "__main__":
    import asyncio

    import yaml
    from loguru import logger

    load_dotenv()

    _yaml_path = (
        Path(__file__).resolve().parents[3]
        / "yaml_files"
        / "services"
        / "agent_service"
        / "openai_chat_agent.yml"
    )
    with open(_yaml_path, encoding="utf-8") as _f:
        _cfg = yaml.safe_load(_f)
    _openai_api_base = _cfg["llm_config"]["configs"]["openai_api_base"]

    # 1. 서비스 인스턴스 생성
    agent_service = AgentFactory.get_agent_service(
        "openai_chat_agent",
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=_openai_api_base,
        model_name="chat_model",
    )

    async def main():
        return await agent_service.is_healthy()

    # 2. Load Image and prepare prompt

    # 3. 서비스의 메인메서드 하나 호출하여 이미지 description 받기
    test = asyncio.run(main())
    if test:
        logger.info(f"성공! 에이전트 상태: {test}")
    else:
        logger.warning("실패.")
