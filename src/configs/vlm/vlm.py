"""Main Vision-Language Model configuration."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .openai import OpenAIVLMConfig


class VLMConfig(BaseModel):
    """Configuration for Vision-Language Model."""

    vlm_model: Literal["openai_compatible",] = Field(
        ..., description="Vision-Language model to use"
    )

    openai_compatible: Optional[OpenAIVLMConfig] = Field(
        None, description="Configuration for OpenAI VLM"
    )
