# config_manager/tts.py
import os
from typing import Literal, Optional

from pydantic import BaseModel, Field


class OpenAIChatAgent(BaseModel):
    """Configuration for OpenAI Chat Agent."""

    openai_api_key: str = Field(
        ..., description="OpenAI API key", default=os.getenv("LLM_API_KEY")
    )
    openai_base_url: str = Field(
        ..., description="Base URL for OpenAI API", default=os.getenv("LLM_BASE_URL")
    )
    model_name: str = Field(
        ...,
        description="Name of the OpenAI LLM model",
        default=os.getenv("LLM_MODEL_NAME"),
    )
    top_p: float = Field(0.9, description="Top-p sampling value (for diversity)")
    temperature: float = Field(
        0.7, description="Sampling temperature (controls creativity)"
    )
    mcp_config: dict = Field(
        {},
        description="MCP client configuration for OpenAI Chat Agent",
    )


class AgentConfig(BaseModel):
    """Configuration for Vision-Language Model."""

    agent_type: Literal["openai",] = Field(
        ..., description="Large-Language model to use"
    )

    openai_chat_agent: Optional[OpenAIChatAgent] = Field(
        None, description="Configuration for OpenAI Chat Agent"
    )
