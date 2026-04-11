"""OpenAI Chat Agent configuration."""

import os

from pydantic import BaseModel, Field


class ShellToolConfig(BaseModel):
    """Configuration for the restricted shell tool."""

    enabled: bool = False
    allowed_commands: list[str] = Field(default_factory=list)


class FilesystemToolConfig(BaseModel):
    """Configuration for the filesystem tool."""

    enabled: bool = False
    root_dir: str = "/tmp/agent-workspace"


class WebSearchToolConfig(BaseModel):
    """Configuration for the web search tool."""

    enabled: bool = False


class BuiltinToolConfig(BaseModel):
    """Configuration for all builtin tools."""

    filesystem: FilesystemToolConfig = Field(default_factory=FilesystemToolConfig)
    shell: ShellToolConfig = Field(default_factory=ShellToolConfig)
    web_search: WebSearchToolConfig = Field(default_factory=WebSearchToolConfig)


class ToolConfig(BaseModel):
    """Top-level tool registry configuration."""

    builtin: BuiltinToolConfig = Field(default_factory=BuiltinToolConfig)


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
    tool_config: ToolConfig | None = Field(
        default=None,
        description="Tool registry configuration for builtin tools (filesystem, shell, web_search)",
    )
