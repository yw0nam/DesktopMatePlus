"""Service initialization and management.

This module provides centralized service initialization using YAML configuration files.
Services are initialized once and stored as module-level singletons.
"""

import asyncio
import threading
from pathlib import Path
from typing import Awaitable, Callable, Optional, TypeVar

import yaml
from loguru import logger

from src.services.agent_service import AgentFactory, AgentService
from src.services.ltm_service import LTMFactory, LTMService
from src.services.stm_service import STMFactory, STMService
from src.services.tts_service import TTSFactory, TTSService
from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper

# Global service instances
_tts_service_instance: Optional[TTSService] = None
_agent_service_instance: Optional[AgentService] = None
_stm_service_instance: Optional[STMService] = None
_ltm_service_instance: Optional[LTMService] = None
_emotion_motion_mapper_instance: Optional[EmotionMotionMapper] = None

T = TypeVar("T")


def _run_async_callable(func: Callable[[], Awaitable[T]]) -> T:
    """Execute an async callable in synchronous context.

    FastAPI lifespan and CLI entry points are synchronous when initializing
    services. Agent health checks are async, so we bridge by running the
    coroutine on the current loop when possible or spinning a dedicated loop.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(func())

    result: dict[str, T] = {}
    error: list[BaseException] = []

    def _runner():
        new_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(new_loop)
            result["value"] = new_loop.run_until_complete(func())
        except BaseException as exc:  # noqa: BLE001 - propagate after join
            error.append(exc)
        finally:
            asyncio.set_event_loop(None)
            new_loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if error:
        raise error[0]

    return result["value"]


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


def _initialize_service(
    service_name: str,
    default_config_path: Path,
    config_key: str,
    factory_fn: Callable[..., T],
    config_path: Optional[str | Path] = None,
    pre_factory_hook: Optional[Callable[[dict, dict], None]] = None,
    async_health_check: bool = False,
    swallow_health_error: bool = False,
) -> T:
    """Shared service initialization: load YAML config, create service, run health check."""
    resolved_path = Path(config_path) if config_path else default_config_path
    config = _load_yaml_config(resolved_path)
    svc_config = config.get(config_key, {})
    service_type = svc_config.get("type")
    service_configs: dict = dict(svc_config.get("configs", {}))

    if pre_factory_hook:
        pre_factory_hook(config, service_configs)

    logger.info(f"🔧 Initializing {service_name} service (type: {service_type})")
    logger.debug(f"{service_name} config: {service_configs}")

    try:
        service = factory_fn(service_type, **service_configs)

        try:
            if async_health_check:
                is_healthy, msg = _run_async_callable(service.is_healthy)
            else:
                is_healthy, msg = service.is_healthy()
            if is_healthy:
                logger.info(
                    f"✅ {service_name} service initialized successfully: {msg}"
                )
            else:
                logger.warning(
                    f"⚠️  {service_name} service initialized but not healthy: {msg}"
                )
        except Exception as health_err:  # noqa: BLE001
            if swallow_health_error:
                logger.error(f"⚠️  {service_name} health check failed: {health_err}")
            else:
                raise

        return service

    except Exception as e:
        logger.error(f"❌ Failed to initialize {service_name} service: {e}")
        raise


_BASE_YAML = Path(__file__).parent.parent.parent / "yaml_files"


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

    _tts_service_instance = _initialize_service(
        service_name="TTS",
        default_config_path=_BASE_YAML / "services" / "tts_service" / "fish_speech.yml",
        config_key="tts_config",
        factory_fn=TTSFactory.get_tts_engine,
        config_path=config_path,
    )
    return _tts_service_instance


def initialize_agent_service(
    config_path: Optional[str | Path] = None, force_reinit: bool = False
) -> AgentService:
    """Initialize Agent service from YAML configuration.

    Args:
        config_path: Path to Agent YAML config file. If None, uses default path.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized Agent service instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If configuration is invalid
    """
    global _agent_service_instance

    if _agent_service_instance is not None and not force_reinit:
        logger.debug("Agent service already initialized, skipping")
        return _agent_service_instance

    def _inject_mcp(config: dict, service_configs: dict) -> None:
        service_configs["mcp_config"] = config.get("mcp_config", None)

    _agent_service_instance = _initialize_service(
        service_name="Agent",
        default_config_path=_BASE_YAML
        / "services"
        / "agent_service"
        / "openai_chat_agent.yml",
        config_key="llm_config",
        factory_fn=AgentFactory.get_agent_service,
        config_path=config_path,
        pre_factory_hook=_inject_mcp,
        async_health_check=True,
        swallow_health_error=True,
    )
    return _agent_service_instance


def initialize_stm_service(
    config_path: Optional[str | Path] = None, force_reinit: bool = False
) -> STMService:
    """Initialize STM service from configuration.

    Args:
        config_path: Path to STM YAML config file. If None, uses default path.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized STM service instance

    Raises:
        ValueError: If configuration is invalid
    """
    global _stm_service_instance

    if _stm_service_instance is not None and not force_reinit:
        logger.debug("STM service already initialized, skipping")
        return _stm_service_instance

    _stm_service_instance = _initialize_service(
        service_name="STM",
        default_config_path=_BASE_YAML / "services" / "stm_service" / "mongodb.yml",
        config_key="stm_config",
        factory_fn=STMFactory.get_stm_service,
        config_path=config_path,
    )
    return _stm_service_instance


def initialize_ltm_service(
    config_path: Optional[str | Path] = None, force_reinit: bool = False
) -> LTMService:
    """Initialize LTM service from configuration.

    Args:
        config_path: Path to LTM YAML config file. If None, uses default path.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized LTM service instance

    Raises:
        ValueError: If configuration is invalid
    """
    global _ltm_service_instance

    if _ltm_service_instance is not None and not force_reinit:
        logger.debug("LTM service already initialized, skipping")
        return _ltm_service_instance

    _ltm_service_instance = _initialize_service(
        service_name="LTM",
        default_config_path=_BASE_YAML / "services" / "ltm_service" / "mem0.yml",
        config_key="ltm_config",
        factory_fn=LTMFactory.get_ltm_service,
        config_path=config_path,
    )
    return _ltm_service_instance


def initialize_services(
    tts_config_path: Optional[str | Path] = None,
    agent_config_path: Optional[str | Path] = None,
    stm_config_path: Optional[str | Path] = None,
    ltm_config_path: Optional[str | Path] = None,
    force_reinit: bool = False,
) -> tuple[TTSService, AgentService, STMService, LTMService]:
    """Initialize all services from YAML configurations.

    Args:
        tts_config_path: Path to TTS YAML config. If None, uses default.
        agent_config_path: Path to Agent YAML config. If None, uses default.
        stm_config_path: Path to STM YAML config. If None, uses default.
        ltm_config_path: Path to LTM YAML config. If None, uses default.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Tuple of (tts_service, agent_service, stm_service, ltm_service)
    """
    logger.info("🚀 Initializing services...")

    tts_service = initialize_tts_service(
        config_path=tts_config_path, force_reinit=force_reinit
    )
    agent_service = initialize_agent_service(
        config_path=agent_config_path, force_reinit=force_reinit
    )
    stm_service = initialize_stm_service(
        config_path=stm_config_path, force_reinit=force_reinit
    )
    ltm_service = initialize_ltm_service(
        config_path=ltm_config_path, force_reinit=force_reinit
    )
    logger.info("✨ All services initialized successfully")

    return tts_service, agent_service, stm_service, ltm_service


def get_tts_service() -> Optional[TTSService]:
    """Get the initialized TTS service instance.

    Returns:
        TTS service instance or None if not initialized
    """
    return _tts_service_instance


def get_agent_service() -> Optional[AgentService]:
    """Get the initialized Agent service instance.

    Returns:
        Agent service instance or None if not initialized
    """
    return _agent_service_instance


def get_stm_service() -> Optional[STMService]:
    """Get the initialized STM service instance.

    Returns:
        STM service instance or None if not initialized
    """
    return _stm_service_instance


def get_ltm_service() -> Optional[LTMService]:
    """Get the initialized LTM service instance.

    Returns:
        LTM service instance or None if not initialized
    """
    return _ltm_service_instance


def initialize_emotion_motion_mapper(
    config_path: Optional[str | Path] = None,
    force_reinit: bool = False,
) -> EmotionMotionMapper:
    """Initialize EmotionMotionMapper from YAML configuration.

    Args:
        config_path: Path to TTS rules YAML config file. If None, uses default path.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized EmotionMotionMapper instance
    """
    global _emotion_motion_mapper_instance

    if _emotion_motion_mapper_instance is not None and not force_reinit:
        logger.debug("EmotionMotionMapper already initialized, skipping")
        return _emotion_motion_mapper_instance

    if config_path is None:
        config_path = (
            Path(__file__).parent.parent.parent / "yaml_files" / "tts_rules.yml"
        )

    config = _load_yaml_config(config_path)
    emotion_map = config.get("emotion_motion_map", {})
    _emotion_motion_mapper_instance = EmotionMotionMapper(emotion_map)
    logger.info("EmotionMotionMapper initialized")
    return _emotion_motion_mapper_instance


def get_emotion_motion_mapper() -> Optional[EmotionMotionMapper]:
    """Get the initialized EmotionMotionMapper instance.

    Returns:
        EmotionMotionMapper instance or None if not initialized
    """
    return _emotion_motion_mapper_instance


__all__ = [
    "initialize_services",
    "initialize_tts_service",
    "initialize_agent_service",
    "initialize_stm_service",
    "initialize_ltm_service",
    "initialize_emotion_motion_mapper",
    "get_tts_service",
    "get_agent_service",
    "get_stm_service",
    "get_ltm_service",
    "get_emotion_motion_mapper",
]
