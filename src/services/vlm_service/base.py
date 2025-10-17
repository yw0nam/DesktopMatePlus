import abc

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.services.vlm_service.prompts import DEFAULT_VLM_SYSTEM_PROMPT


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
            image (str | bytes): The image to include in the request, either as a URL or base64.

        TODO: Add support for different image input types.
        TODO: Add support of video, multi-image inputs.
        Returns:
            str: The model's response.
        """
        if isinstance(image, str):
            input_image_dict = {"type": "image", "source_type": "url", "url": image}
        elif isinstance(image, bytes):
            input_image_dict = {
                "type": "image",
                "source_type": "base64",
                "data": image,
                "mime_type": "image/jpeg",
            }
        else:
            raise ValueError("Invalid image type")

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
