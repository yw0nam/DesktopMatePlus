"""Application settings and configuration."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings.

    These settings can be overridden using environment variables with the
    FASTAPI_ prefix. For example, set FASTAPI_PORT=9000 to change the port.
    """

    # Server configuration
    host: str = Field(default="127.0.0.1", description="Server host address")
    port: int = Field(default=8000, description="Server port number")

    # CORS configuration
    cors_origins: List[str] = Field(default=["*"], description="Allowed CORS origins")

    # Application metadata
    app_name: str = Field(
        default="DesktopMate+ Backend", description="Application name"
    )
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    model_config = SettingsConfigDict(
        env_prefix="FASTAPI_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create a singleton instance
settings = Settings()
