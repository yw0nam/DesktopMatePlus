from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.services.vlm_service.prompts import DEFAULT_VLM_SYSTEM_PROMPT
from src.services.vlm_service.utils import prepare_image_for_vlm


class VLMService(ABC):
    def __init__(self):
        self.model = self.initialize_model()

    @abstractmethod
    def initialize_model(self) -> BaseChatModel:
        pass

    def health_check(self) -> bool:
        try:
            self.model.invoke([HumanMessage(content="Health check")])
            return True
        except Exception as e:
            print(f"Health check failed: {e}")
            return False

    def generate_response(
        self, image: str | bytes, prompt: str = "Describe this image"
    ) -> str:
        """Generate a response from the model based on the prompt and image.

        Args:
            image (str | bytes): The image to include in the request, either as a URL or raw bytes.
            prompt (str): The text prompt to send to the model. Default is "Describe this image".

        TODO: Add support of video, multi-image inputs.
        Returns:
            str: The model's response.
        """
        # Use utility function to prepare image for VLM API
        input_image_dict = prepare_image_for_vlm(image)

        message = [
            SystemMessage(content=DEFAULT_VLM_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    input_image_dict,
                ]
            ),
        ]
        response = self.model.invoke(message)
        return response.content
