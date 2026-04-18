"""OpenAI Chat Agent configuration."""

import os

from pydantic import BaseModel, Field


class OpenAIChatAgentConfig(BaseModel):
    """Configuration for OpenAI Chat Agent."""

    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("LLM_API_KEY"),
        description="API key for OpenAI API",
    )
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
    mcp_config: dict | None = Field(
        default=None,
        description="MCP client configuration for OpenAI Chat Agent",
    )
    support_image: bool = Field(
        default=False,
        description="Whether the agent supports image inputs in messages",
    )
    filesystem_root_dir: str = Field(
        default="/tmp/agent-workspace",
        description="Sandbox root for filesystem tools (ReadFile/WriteFile/EditFile/etc).",
    )
