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

    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the VLM provider is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        try:
            self.model.invoke([HumanMessage(content="Health check")])
            return True, "VLM service is healthy"
        except Exception as e:
            return False, f"VLM health check failed: {str(e)}"

    def generate_response(
        self,
        image: str | bytes | list[str | bytes],
        prompt: str = "Describe this image",
    ) -> str:
        """Generate a response from the model based on the prompt and image.

        Args:
            image (str | bytes | list): The image(s) to include in the request, either as a URL, raw bytes, or list.
            prompt (str): The text prompt to send to the model. Default is "Describe this image".

        TODO: Add support of video, multi-image inputs.
        Returns:
            str: The model's response.
        """
        # Use utility function to prepare image for VLM API
        input_image_dict = prepare_image_for_vlm(image)

        # Build content list with text and image(s)
        content = [{"type": "text", "text": prompt}]
        if isinstance(input_image_dict, list):
            content.extend(input_image_dict)
        else:
            content.append(input_image_dict)

        message = [
            SystemMessage(content=DEFAULT_VLM_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
        response = self.model.invoke(message)
        return response.content
