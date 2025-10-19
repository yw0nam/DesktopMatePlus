# config_manager/tts.py
import os
from typing import Literal, Optional

from pydantic import BaseModel, Field


class OpenAIVLMConfig(BaseModel):
    """Configuration for OpenAI VLM."""

    openai_api_key: str = Field(
        ..., description="OpenAI API key", default=os.getenv("VLM_API_KEY")
    )
    openai_base_url: str = Field(
        ..., description="Base URL for OpenAI API", default=os.getenv("VLM_BASE_URL")
    )
    model_name: str = Field(
        ...,
        description="Name of the OpenAI VLM model",
        default=os.getenv("VLM_MODEL_NAME"),
    )
    top_p: float = Field(0.9, description="Top-p sampling value (for diversity)")
    temperature: float = Field(
        0.7, description="Sampling temperature (controls creativity)"
    )


class VLMConfig(BaseModel):
    """Configuration for Vision-Language Model."""

    vlm_model: Literal["openai",] = Field(
        ..., description="Vision-Language model to use"
    )

    openai_vlm: Optional[OpenAIVLMConfig] = Field(
        None, description="Configuration for OpenAI VLM"
    )
