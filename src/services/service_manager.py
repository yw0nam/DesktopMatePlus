"""Service initialization and management.

This module provides centralized service initialization using YAML configuration files.
Services are initialized once and stored as module-level singletons.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from src.services.tts_service import TTSService
from src.services.tts_service.tts_factory import TTSFactory
from src.services.vlm_service import VLMService
from src.services.vlm_service.vlm_factory import VLMFactory

# Global service instances
_tts_service_instance: Optional[TTSService] = None
_vlm_service_instance: Optional[VLMService] = None


def _load_yaml_config(yaml_path: str | Path) -> dict:
    """Load YAML configuration file.

    Args:
        yaml_path: Path to YAML configuration file

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def initialize_tts_service(
    config_path: Optional[str | Path] = None, force_reinit: bool = False
) -> TTSService:
    """Initialize TTS service from YAML configuration.

    Args:
        config_path: Path to TTS YAML config file. If None, uses default path.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized TTS service instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If configuration is invalid
    """
    global _tts_service_instance

    if _tts_service_instance is not None and not force_reinit:
        logger.debug("TTS service already initialized, skipping")
        return _tts_service_instance

    # Default config path
    if config_path is None:
        config_path = (
            Path(__file__).parent.parent.parent
            / "yaml_files"
            / "services"
            / "tts_service"
            / "fish_speech.yml"
        )

    # Load configuration
    config = _load_yaml_config(config_path)
    tts_config = config.get("tts_config", {})

    service_type = tts_config.get("type", "fish_local_tts")
    service_configs = tts_config.get("configs", {})

    # Override with environment variables if present
    if "base_url" in service_configs:
        service_configs["base_url"] = os.getenv(
            "TTS_BASE_URL", service_configs["base_url"]
        )

    # Add API key from environment if available
    api_key = os.getenv("TTS_API_KEY")
    if api_key:
        service_configs["api_key"] = api_key

    # Create TTS engine using factory with **configs
    logger.info(f"🔧 Initializing TTS service (type: {service_type})")
    logger.debug(f"TTS config: {service_configs}")

    try:
        tts_engine = TTSFactory.get_tts_engine(service_type, **service_configs)

        _tts_service_instance = tts_engine

        # Health check
        is_healthy, msg = tts_engine.is_healthy()
        if is_healthy:
            logger.info(f"✅ TTS service initialized successfully: {msg}")
        else:
            logger.warning(f"⚠️  TTS service initialized but not healthy: {msg}")

        return _tts_service_instance

    except Exception as e:
        logger.error(f"❌ Failed to initialize TTS service: {e}")
        raise


def initialize_vlm_service(
    config_path: Optional[str | Path] = None, force_reinit: bool = False
) -> VLMService:
    """Initialize VLM service from YAML configuration.

    Args:
        config_path: Path to VLM YAML config file. If None, uses default path.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized VLM service instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If configuration is invalid
    """
    global _vlm_service_instance

    if _vlm_service_instance is not None and not force_reinit:
        logger.debug("VLM service already initialized, skipping")
        return _vlm_service_instance

    # Default config path
    if config_path is None:
        config_path = (
            Path(__file__).parent.parent.parent
            / "yaml_files"
            / "services"
            / "vlm_service"
            / "openai_compatible.yml"
        )

    # Load configuration
    config = _load_yaml_config(config_path)
    vlm_config = config.get("vlm_config", {})

    service_type = vlm_config.get("type", "openai")
    service_configs = vlm_config.get("configs", {})

    # Get credentials from environment variables (required)
    openai_api_base = os.getenv("VLM_BASE_URL", "http://localhost:8001")
    model_name = os.getenv("VLM_MODEL_NAME", "chat_model")
    openai_api_key = os.getenv(
        "VLM_API_KEY", "dummy-key"
    )  # Default to dummy key for local servers

    # Add to service configs
    service_configs["openai_api_base"] = openai_api_base
    service_configs["model_name"] = model_name
    service_configs["openai_api_key"] = openai_api_key

    # Create VLM engine using factory with **configs
    logger.info(
        f"🔧 Initializing VLM service (type: {service_type}, model: {model_name})"
    )
    logger.debug(f"VLM config: {service_configs}")

    try:
        vlm_engine = VLMFactory.get_vlm_service(service_type, **service_configs)

        _vlm_service_instance = vlm_engine

        # Health check
        is_healthy, msg = vlm_engine.is_healthy()
        if is_healthy:
            logger.info(f"✅ VLM service initialized successfully: {msg}")
        else:
            logger.warning(f"⚠️  VLM service initialized but not healthy: {msg}")

        return _vlm_service_instance

    except Exception as e:
        logger.error(f"❌ Failed to initialize VLM service: {e}")
        raise


def initialize_services(
    tts_config_path: Optional[str | Path] = None,
    vlm_config_path: Optional[str | Path] = None,
    force_reinit: bool = False,
) -> tuple[TTSService, VLMService]:
    """Initialize all services from YAML configurations.

    This is the main entry point for service initialization. It loads
    configurations from YAML files and creates service instances.

    Args:
        tts_config_path: Path to TTS YAML config. If None, uses default.
        vlm_config_path: Path to VLM YAML config. If None, uses default.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Tuple of (tts_service, vlm_service)

    Example:
        >>> tts_service, vlm_service = initialize_services()
        >>> # Use services...
    """
    logger.info("🚀 Initializing services...")

    # Initialize TTS service
    tts_service = initialize_tts_service(
        config_path=tts_config_path, force_reinit=force_reinit
    )

    # Initialize VLM service
    vlm_service = initialize_vlm_service(
        config_path=vlm_config_path, force_reinit=force_reinit
    )

    logger.info("✨ All services initialized successfully")

    return tts_service, vlm_service


def get_tts_service() -> Optional[TTSService]:
    """Get the initialized TTS service instance.

    Returns:
        TTS service instance or None if not initialized
    """
    return _tts_service_instance


def get_vlm_service() -> Optional[VLMService]:
    """Get the initialized VLM service instance.

    Returns:
        VLM service instance or None if not initialized
    """
    return _vlm_service_instance


__all__ = [
    "initialize_services",
    "initialize_tts_service",
    "initialize_vlm_service",
    "get_tts_service",
    "get_vlm_service",
]
