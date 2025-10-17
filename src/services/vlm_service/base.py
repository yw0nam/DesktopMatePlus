import abc

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.services.vlm_service.prompts import DEFAULT_VLM_SYSTEM_PROMPT
from src.services.vlm_service.utils import prepare_image_for_vlm


class BaseVLMService(abc.ABC):
    def __init__(self, temperature: float, top_p: float):
        self.temperature = temperature
        self.top_p = top_p
        self.model = self.initialize_model()

    @abc.abstractmethod
    def initialize_model(self) -> BaseChatModel:
        pass

    def health_check(self) -> bool:
        try:
            self.model.invoke([HumanMessage(content="Health check")])
            return True
        except Exception as e:
            print(f"Health check failed: {e}")
            return False

    def generate_response(self, prompt: str, image: str | bytes) -> str:
        """Generate a response from the model based on the prompt and image.

        Args:
            prompt (str): The text prompt to send to the model.
            image (str | bytes): The image to include in the request, either as a URL or raw bytes.

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
