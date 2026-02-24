"""Main agent configuration."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .openai_chat_agent import OpenAIChatAgentConfig


class AgentConfig(BaseModel):
    """Configuration for Vision-Language Model."""

    agent_type: Literal["openai",] = Field(
        ..., description="Large-Language model to use"
    )

    openai_chat_agent: Optional[OpenAIChatAgentConfig] = Field(
        None, description="Configuration for OpenAI Chat Agent"
    )
