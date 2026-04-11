"""Service initialization and management.

This module provides centralized service initialization using YAML configuration files.
Services are initialized once and stored as module-level singletons.
"""

import asyncio
import os
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from src.services.channel_service.slack_service import SlackService, SlackSettings
    from src.services.task_sweep_service.sweep import BackgroundSweepService

import pymongo as _pymongo
import yaml
from loguru import logger

from src.core.error_classifier import ErrorClassifier, ErrorSeverity
from src.services.agent_service import AgentFactory, AgentService
from src.services.agent_service.session_registry import SessionRegistry
from src.services.ltm_service import LTMFactory, LTMService
from src.services.summary_service import SummaryService
from src.services.tts_service import TTSFactory, TTSService
from src.services.tts_service.emotion_motion_mapper import EmotionMotionMapper
from src.services.user_profile_service import UserProfileService

# Global service instances
_tts_service_instance: TTSService | None = None
_agent_service_instance: AgentService | None = None
_ltm_service_instance: LTMService | None = None
_emotion_motion_mapper_instance: EmotionMotionMapper | None = None
_mongo_client: "_pymongo.MongoClient | None" = None
_mongo_db: "_pymongo.database.Database | None" = None
_session_registry_instance: "SessionRegistry | None" = None
_user_profile_service_instance: UserProfileService | None = None
_summary_service_instance: SummaryService | None = None

T = TypeVar("T")


def _run_async_callable[T](func: Callable[[], Awaitable[T]]) -> T:
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
        except BaseException as exc:
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

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def _initialize_service[T](
    service_name: str,
    default_config_path: Path,
    config_key: str,
    factory_fn: Callable[..., T],
    config_path: str | Path | None = None,
    pre_factory_hook: Callable[[dict, dict], None] | None = None,
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
        except Exception as health_err:
            if swallow_health_error:
                logger.error(f"⚠️  {service_name} health check failed: {health_err}")
            else:
                raise

        return service

    except Exception as e:
        severity = ErrorClassifier.classify(e)
        if severity == ErrorSeverity.TRANSIENT:
            logger.warning(
                f"⚠️  {service_name} init failed (transient, may recover): {e}"
            )
        else:
            logger.error(
                f"❌ Failed to initialize {service_name} service [{severity}]: {e}"
            )
        raise


_BASE_YAML = Path(__file__).parent.parent.parent / "yaml_files"


def initialize_mongodb_client(
    config_path: str | Path | None = None, force_reinit: bool = False
) -> "_pymongo.MongoClient":
    """Initialize shared MongoDB client for checkpointer and session_registry."""
    global _mongo_client, _mongo_db, _session_registry_instance
    if _mongo_client is not None and not force_reinit:
        logger.debug("MongoDB client already initialized, skipping")
        return _mongo_client

    resolved = (
        Path(config_path)
        if config_path
        else _BASE_YAML / "services" / "checkpointer.yml"
    )
    cfg = _load_yaml_config(resolved).get("checkpointer_config", {})
    connection_string: str = cfg["connection_string"]
    db_name: str = cfg["db_name"]

    _mongo_client = _pymongo.MongoClient(
        connection_string, uuidRepresentation="standard"
    )
    try:
        _mongo_client.admin.command("ping")
    except Exception as e:
        logger.error(f"❌ MongoDB client ping failed: {e}")
        raise
    _mongo_db = _mongo_client[db_name]
    _session_registry_instance = SessionRegistry(_mongo_db["session_registry"])
    logger.info(f"MongoDB client initialized (db={db_name})")
    return _mongo_client


def get_mongo_client() -> "_pymongo.MongoClient | None":
    """Get the initialized MongoDB client instance."""
    return _mongo_client


def reset_mongo_client() -> None:
    """Reset the MongoDB client singleton to None.

    Call this after closing the client so that a subsequent call to
    initialize_mongodb_client() creates a fresh connection instead of
    reusing the already-closed client.
    """
    global _mongo_client, _mongo_db, _session_registry_instance
    _mongo_client = None
    _mongo_db = None
    _session_registry_instance = None


def get_mongo_db() -> "_pymongo.database.Database | None":
    """Get the initialized MongoDB database instance."""
    return _mongo_db


def get_session_registry() -> "SessionRegistry | None":
    """Get the initialized SessionRegistry instance."""
    return _session_registry_instance


def initialize_user_profile_service(
    force_reinit: bool = False,
) -> UserProfileService:
    """Initialize UserProfileService using the shared MongoDB client.

    Args:
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized UserProfileService instance

    Raises:
        RuntimeError: If MongoDB client is not yet initialized
    """
    global _user_profile_service_instance

    if _user_profile_service_instance is not None and not force_reinit:
        logger.debug("UserProfileService already initialized, skipping")
        return _user_profile_service_instance

    if _mongo_db is None:
        raise RuntimeError(
            "MongoDB client not initialized — call initialize_mongodb_client() first"
        )

    collection = _mongo_db["user_profiles"]
    _user_profile_service_instance = UserProfileService(collection=collection)
    logger.info("✅ UserProfileService initialized (collection=user_profiles)")
    return _user_profile_service_instance


def get_user_profile_service() -> UserProfileService | None:
    """Get the initialized UserProfileService instance."""
    return _user_profile_service_instance


def initialize_summary_service(
    force_reinit: bool = False,
) -> SummaryService:
    """Initialize SummaryService using the shared MongoDB client and agent LLM.

    Args:
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Initialized SummaryService instance

    Raises:
        RuntimeError: If MongoDB client is not yet initialized
    """
    global _summary_service_instance

    if _summary_service_instance is not None and not force_reinit:
        logger.debug("SummaryService already initialized, skipping")
        return _summary_service_instance

    if _mongo_db is None:
        raise RuntimeError(
            "MongoDB client not initialized — call initialize_mongodb_client() first"
        )

    from langchain_openai import ChatOpenAI

    if _agent_service_instance is not None and hasattr(_agent_service_instance, "llm"):
        llm = _agent_service_instance.llm
    else:
        logger.warning(
            "Summary service: agent LLM not available, falling back to default ChatOpenAI"
        )
        llm = ChatOpenAI(temperature=0.3)

    collection = _mongo_db["conversation_summaries"]
    _summary_service_instance = SummaryService(collection=collection, llm=llm)
    logger.info("✅ SummaryService initialized (collection=conversation_summaries)")
    return _summary_service_instance


def get_summary_service() -> SummaryService | None:
    """Get the initialized SummaryService instance."""
    return _summary_service_instance


def initialize_tts_service(
    config_path: str | Path | None = None, force_reinit: bool = False
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

    def _apply_tts_env_overrides(_full_cfg: dict, svc_cfg: dict) -> None:
        if _full_cfg.get("tts_config", {}).get("type") != "irodori":
            return
        env_url = os.getenv("IRODORI_TTS_BASE_URL")
        if env_url:
            logger.info("TTS base_url overridden via IRODORI_TTS_BASE_URL env var")
            svc_cfg["base_url"] = env_url

    _tts_service_instance = _initialize_service(
        service_name="TTS",
        default_config_path=_BASE_YAML / "services" / "tts_service" / "irodori.yml",
        config_key="tts_config",
        factory_fn=TTSFactory.get_tts_engine,
        config_path=config_path,
        pre_factory_hook=_apply_tts_env_overrides,
    )
    return _tts_service_instance


def initialize_agent_service(
    config_path: str | Path | None = None,
    force_reinit: bool = False,
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
        service_configs["mcp_config"] = config.get("mcp_config")

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


def initialize_ltm_service(
    config_path: str | Path | None = None, force_reinit: bool = False
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
    tts_config_path: str | Path | None = None,
    agent_config_path: str | Path | None = None,
    ltm_config_path: str | Path | None = None,
    force_reinit: bool = False,
) -> tuple[TTSService, AgentService, LTMService]:
    """Initialize all services from YAML configurations.

    Args:
        tts_config_path: Path to TTS YAML config. If None, uses default.
        agent_config_path: Path to Agent YAML config. If None, uses default.
        ltm_config_path: Path to LTM YAML config. If None, uses default.
        force_reinit: If True, reinitialize even if already initialized.

    Returns:
        Tuple of (tts_service, agent_service, ltm_service)
    """
    logger.info("🚀 Initializing services...")

    tts_service = initialize_tts_service(
        config_path=tts_config_path, force_reinit=force_reinit
    )
    agent_service = initialize_agent_service(
        config_path=agent_config_path, force_reinit=force_reinit
    )
    ltm_service = initialize_ltm_service(
        config_path=ltm_config_path, force_reinit=force_reinit
    )
    logger.info("✨ All services initialized successfully")

    return tts_service, agent_service, ltm_service


def get_tts_service() -> TTSService | None:
    """Get the initialized TTS service instance.

    Returns:
        TTS service instance or None if not initialized
    """
    return _tts_service_instance


def get_agent_service() -> AgentService | None:
    """Get the initialized Agent service instance.

    Returns:
        Agent service instance or None if not initialized
    """
    return _agent_service_instance


def get_ltm_service() -> LTMService | None:
    """Get the initialized LTM service instance.

    Returns:
        LTM service instance or None if not initialized
    """
    return _ltm_service_instance


def initialize_emotion_motion_mapper(
    config_path: str | Path | None = None,
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


def get_emotion_motion_mapper() -> EmotionMotionMapper | None:
    """Get the initialized EmotionMotionMapper instance.

    Returns:
        EmotionMotionMapper instance or None if not initialized
    """
    return _emotion_motion_mapper_instance


def _load_service_yaml(
    service_name: str,
    default_config_path: Path,
    config_key: str,
    config_path: str | Path | None = None,
) -> dict:
    """Load YAML config and extract a named section, with a missing-file warning fallback.

    Unlike ``_load_yaml_config``, this helper does *not* raise when the file is
    absent — it logs a warning and returns an empty dict so callers can apply
    their own defaults.

    Args:
        service_name: Human-readable label used in log messages.
        default_config_path: Default YAML file path used when ``config_path`` is None.
        config_key: Top-level key to extract from the loaded YAML document.
        config_path: Explicit override path; falls back to ``default_config_path``.

    Returns:
        Dict extracted from ``config_key``, or ``{}`` when the file is missing or
        the key is absent.
    """
    resolved = Path(config_path) if config_path else default_config_path
    if not resolved.exists():
        logger.warning(f"{service_name} config not found at {resolved}, using defaults")
        return {}
    raw = _load_yaml_config(resolved)
    if not isinstance(raw, dict):
        return {}
    val = raw.get(config_key)
    return val if isinstance(val, dict) else {}


def initialize_channel_service(
    config_path: str | Path | None = None,
) -> "SlackSettings":
    """Build SlackSettings from YAML configuration with env-var fallbacks.

    Reads the ``slack`` section from the channel service YAML config.
    If ``bot_token`` or ``signing_secret`` are absent/empty in the file,
    ``SLACK_BOT_TOKEN`` and ``SLACK_SIGNING_SECRET`` env vars are used.

    Args:
        config_path: Path to channel service YAML config. If None, uses default.

    Returns:
        SlackSettings instance (enabled flag + credentials resolved).
    """
    import os

    from src.services.channel_service.slack_service import SlackSettings

    slack_cfg = _load_service_yaml(
        service_name="Channel",
        default_config_path=_BASE_YAML / "services" / "channel_service" / "channel.yml",
        config_key="slack",
        config_path=config_path,
    )

    if not slack_cfg.get("bot_token"):
        slack_cfg["bot_token"] = os.getenv("SLACK_BOT_TOKEN", "")
    if not slack_cfg.get("signing_secret"):
        slack_cfg["signing_secret"] = os.getenv("SLACK_SIGNING_SECRET", "")

    return SlackSettings(**slack_cfg)


def initialize_sweep_service(
    agent_service: AgentService,
    session_registry: SessionRegistry,
    config_path: str | Path | None = None,
    slack_service_fn: Callable[[], "SlackService | None"] | None = None,
) -> "BackgroundSweepService":
    """Build BackgroundSweepService from YAML configuration.

    Reads the ``sweep_config`` section from the task sweep YAML config.
    Falls back to SweepConfig defaults when the section is absent.

    Args:
        agent_service: Initialized AgentService instance (required).
        session_registry: Initialized SessionRegistry instance (required).
        config_path: Path to sweep service YAML config. If None, uses default.
        slack_service_fn: Optional callable returning SlackService for notifications.

    Returns:
        Configured BackgroundSweepService (not yet started).
    """
    from src.services.task_sweep_service.sweep import (
        BackgroundSweepService,
        SweepConfig,
    )

    sweep_cfg_dict = _load_service_yaml(
        service_name="Sweep",
        default_config_path=_BASE_YAML
        / "services"
        / "task_sweep_service"
        / "sweep.yml",
        config_key="sweep_config",
        config_path=config_path,
    )
    sweep_cfg = SweepConfig(**sweep_cfg_dict)

    return BackgroundSweepService(
        agent_service=agent_service,
        session_registry=session_registry,
        config=sweep_cfg,
        slack_service_fn=slack_service_fn,
    )


__all__ = [
    "get_agent_service",
    "get_emotion_motion_mapper",
    "get_ltm_service",
    "get_mongo_client",
    "get_mongo_db",
    "get_session_registry",
    "get_summary_service",
    "get_tts_service",
    "get_user_profile_service",
    "initialize_agent_service",
    "initialize_channel_service",
    "initialize_emotion_motion_mapper",
    "initialize_ltm_service",
    "initialize_mongodb_client",
    "initialize_services",
    "initialize_summary_service",
    "initialize_sweep_service",
    "initialize_tts_service",
    "initialize_user_profile_service",
    "reset_mongo_client",
]
