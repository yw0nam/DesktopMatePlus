import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.services.vlm_service.base import BaseVLMService


class OpenAIService(BaseVLMService):
    def initialize_model(self) -> BaseChatModel:
        """Initialize the OpenAI chat model.

        Returns:
            BaseChatModel: The initialized chat model.
        """
        return ChatOpenAI(
            temperature=self.temperature,
            top_p=self.top_p,
            openai_api_key=os.getenv("VLM_API_KEY"),
            model_name=os.getenv("VLM_MODEL_NAME"),
            openai_api_base=os.getenv("VLM_BASE_URL"),
        )
