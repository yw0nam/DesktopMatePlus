import os
from typing import Dict, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

_LLM_API_KEY = os.getenv("LLM_API_KEY")


class OpenAIChatAgentConfig(BaseModel):
    """Configuration for OpenAI Chat Agent."""

    openai_api_key: str = Field(description="OpenAI API key", default=_LLM_API_KEY)
    openai_api_base: str = Field(
        description="Base URL for OpenAI API", default="http://localhost:55120/v1"
    )
    model_name: str = Field(
        description="Name of the OpenAI LLM model",
        default="chat_model",
    )
    top_p: float = Field(0.9, description="Top-p sampling value (for diversity)")
    temperature: float = Field(
        0.7, description="Sampling temperature (controls creativity)"
    )
    mcp_config: Optional[Dict] = Field(
        default=None,
        description="MCP client configuration for OpenAI Chat Agent",
    )


class AgentConfig(BaseModel):
    """Configuration for Vision-Language Model."""

    agent_type: Literal["openai",] = Field(
        ..., description="Large-Language model to use"
    )

    openai_chat_agent: Optional[OpenAIChatAgentConfig] = Field(
        None, description="Configuration for OpenAI Chat Agent"
    )
