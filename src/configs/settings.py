"""Application settings and configuration."""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class WebSocketConfig(BaseModel):
    """WebSocket connection configuration."""

    max_error_tolerance: int = Field(
        default=5,
        ge=1,
        description="Maximum consecutive errors before closing connection",
    )
    error_backoff_seconds: float = Field(
        default=0.5, ge=0, description="Seconds to wait after transient errors"
    )
    inactivity_timeout_seconds: int = Field(
        default=300,
        ge=0,
        description="Seconds of inactivity before closing connection",
    )


class Settings(BaseModel):
    """Application configuration settings.

    This class validates configuration loaded from YAML files.
    Similar to service configs (e.g., MongoDBShortTermMemoryConfig),
    it uses Pydantic for validation and type checking.
    """

    # Server configuration
    host: str = Field(default="127.0.0.1", description="Server host address")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port number")

    # CORS configuration
    cors_origins: List[str] = Field(default=["*"], description="Allowed CORS origins")

    # Application metadata
    app_name: str = Field(
        default="DesktopMate+ Backend", description="Application name"
    )
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Health check settings
    health_check_timeout: int = Field(
        default=5, description="Timeout for health checks in seconds"
    )

    # WebSocket configuration
    websocket: WebSocketConfig = Field(
        default_factory=WebSocketConfig, description="WebSocket configuration"
    )


def load_settings_from_yaml(yaml_file: str | Path) -> Settings:
    """Load and validate settings from YAML configuration file.

    Args:
        yaml_file: Path to YAML configuration file

    Returns:
        Settings: Validated settings instance

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid
    """
    yaml_path = Path(yaml_file)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Extract settings section from config
    settings_dict = config.get("settings", {})

    # Validate and create Settings instance
    return Settings(**settings_dict)


# Global settings instance (will be initialized from YAML in main.py)
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the current settings instance.

    Returns:
        Settings: Current application settings

    Raises:
        RuntimeError: If settings haven't been initialized
    """
    if settings is None:
        raise RuntimeError(
            "Settings not initialized. Call load_settings_from_yaml() first."
        )
    return settings


def initialize_settings(yaml_file: str | Path) -> Settings:
    """Initialize global settings from YAML file.

    Args:
        yaml_file: Path to YAML configuration file

    Returns:
        Settings: Initialized settings instance
    """
    global settings
    settings = load_settings_from_yaml(yaml_file)
    return settings
