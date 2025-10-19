from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.services.vlm_service.service import VLMService


class OpenAIService(VLMService):
    """Service for interacting with OpenAI's language models."""

    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str = None,
        openai_api_base: str = None,
        model_name: str = None,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        super().__init__()

    def initialize_model(self) -> BaseChatModel:
        """Initialize the OpenAI chat model.

        Returns:
            BaseChatModel: The initialized chat model.
        """
        return ChatOpenAI(
            temperature=self.temperature,
            top_p=self.top_p,
            api_key=self.openai_api_key,
            model_name=self.model_name,
            base_url=self.openai_api_base,
        )
