"""OpenAI Vision-Language Model configuration."""

import os

from pydantic import BaseModel, Field


class OpenAIVLMConfig(BaseModel):
    """Configuration for OpenAI VLM."""

    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("VLM_API_KEY"),
        description="API key for OpenAI API",
    )
    openai_api_base: str = Field(
        description="Base URL for OpenAI API", default="http://localhost:5530/v1"
    )
    model_name: str = Field(
        description="Name of the OpenAI VLM model",
        default="chat_model",
    )
    top_p: float = Field(0.9, description="Top-p sampling value (for diversity)")
    temperature: float = Field(
        0.7, description="Sampling temperature (controls creativity)"
    )
