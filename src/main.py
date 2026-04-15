"""FastAPI application entry point."""

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes import router as api_router
from src.configs.settings import get_settings, initialize_settings
from src.core.logger import setup_logging
from src.core.middleware import RequestIDMiddleware

if TYPE_CHECKING:
    from src.services.proactive_service.proactive_service import ProactiveService
    from src.services.task_sweep_service.sweep import BackgroundSweepService

load_dotenv()


def load_main_config(yaml_file: str | Path) -> dict:
    """Load main configuration file that references service configs.

    This function:
    1. Initializes settings from YAML using the validator pattern
    2. Resolves service config paths relative to main.yml location

    Args:
        yaml_file: Path to main.yml configuration file

    Returns:
        Dictionary with service configuration paths
    """
    yaml_path = Path(yaml_file)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    # Initialize settings using validator pattern (like stm_factory)
    initialize_settings(yaml_path)

    # Load config for service paths
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Resolve services config path relative to main.yml location
    base_dir = yaml_path.parent
    services_file = config.get("services_file")

    resolved_paths = {}
    if services_file:
        resolved_paths["services_config_path"] = base_dir / services_file

    return resolved_paths


def create_app(config_paths: dict | None = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        config_paths: Dictionary of service config paths. Captured by lifespan closure.
    """
    if config_paths is None:
        config_paths = {}

    settings = get_settings()

    async def _startup() -> (
        "tuple[BackgroundSweepService | None, ProactiveService | None]"
    ):
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_retention = os.getenv("LOG_RETENTION", "30 days")
        setup_logging(level=log_level, retention=log_retention)

        logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
        logger.info(
            f"📝 API Documentation: http://{settings.host}:{settings.port}/docs"
        )
        logger.info(f"🔧 Debug mode: {settings.debug}")
        logger.info(f"📊 Log level: {log_level} | Retention: {log_retention}")

        sweep_service: BackgroundSweepService | None = None
        proactive_service: ProactiveService | None = None

        try:
            from src.services import (
                get_agent_service,
                initialize_agent_service,
                initialize_emotion_motion_mapper,
                initialize_ltm_service,
                initialize_mongodb_client,
                initialize_tts_service,
                initialize_user_profile_service,
            )

            svc_config = config_paths.get("services_config_path")
            logger.info(f"📋 Loading service configurations from {svc_config}")

            initialize_tts_service(config_path=svc_config)

            initialize_emotion_motion_mapper()

            # MongoDB client for checkpointer + session_registry (before agent)
            initialize_mongodb_client(config_path=svc_config)

            try:
                initialize_user_profile_service()
                logger.info("User profile service initialized")
            except Exception:
                logger.exception("Failed to initialize user profile service")

            initialize_agent_service(config_path=svc_config)

            initialize_ltm_service(config_path=svc_config)

            # Async initialization: MCP tools + agent creation
            agent_svc = get_agent_service()
            if agent_svc is not None:
                await agent_svc.initialize_async()
                logger.info("Agent async initialization complete")

            try:
                from src.services import initialize_summary_service

                initialize_summary_service()
                logger.info("Summary service initialized")
            except Exception:
                logger.exception("Failed to initialize summary service")

            # Channel service (Slack 등 외부 채널)
            try:
                from src.services.channel_service import init_channel_service
                from src.services.service_manager import initialize_channel_service

                slack_settings = initialize_channel_service(config_path=svc_config)
                await init_channel_service(slack_settings)
                logger.info("Channel service initialized")
            except Exception:
                logger.exception("Failed to initialize channel service")

            try:
                from src.services.channel_service import get_slack_service
                from src.services.service_manager import (
                    get_pending_task_repo,
                    initialize_sweep_service,
                )

                pending_repo = get_pending_task_repo()
                if pending_repo is not None:
                    sweep_service = initialize_sweep_service(
                        pending_task_repo=pending_repo,
                        config_path=svc_config,
                        slack_service_fn=get_slack_service,
                    )
                    await sweep_service.start()
                    logger.info(
                        f"Task sweep started "
                        f"(interval={sweep_service.config.sweep_interval_seconds}s, "
                        f"ttl={sweep_service.config.task_ttl_seconds}s)"
                    )
                else:
                    logger.warning(
                        "Task sweep skipped: pending task repository not available"
                    )
            except Exception:
                logger.exception("Failed to start background sweep service")

            # Proactive talking service
            try:
                from src.services.service_manager import initialize_proactive_service
                from src.services.websocket_service.manager import (
                    websocket_manager as _ws_mgr,
                )

                agent_svc = get_agent_service()
                if agent_svc is not None:
                    proactive_service = initialize_proactive_service(
                        ws_manager=_ws_mgr,
                        agent_service=agent_svc,
                        config_path=svc_config,
                    )
                    await proactive_service.start()
                    logger.info("Proactive service started")
                else:
                    logger.warning(
                        "Proactive service skipped: agent service not available"
                    )
            except Exception:
                logger.exception("Failed to start proactive service")

        except Exception:
            logger.exception("⚠️  Failed to initialize services")

        return sweep_service, proactive_service

    async def _shutdown(
        sweep_service: "BackgroundSweepService | None",
        proactive_service: "ProactiveService | None",
    ) -> None:
        logger.info(f"👋 Shutting down {settings.app_name}")

        # Shutdown in reverse init order: proactive → sweep → channel → websocket → mongo

        if proactive_service is not None:
            try:
                await proactive_service.stop()
                logger.info("Proactive service stopped")
            except Exception:
                logger.exception("Error stopping proactive service")

        if sweep_service is not None:
            try:
                await sweep_service.stop()
                logger.info("Task sweep service stopped")
            except Exception:
                logger.exception("Error stopping sweep service")

        try:
            from src.services import get_agent_service

            agent_svc = get_agent_service()
            if agent_svc is not None:
                await agent_svc.cleanup_async()
        except Exception:
            logger.exception("Error cleaning up agent MCP client")

        try:
            from src.services.channel_service import cleanup_channel_service

            await cleanup_channel_service()
        except Exception:
            logger.exception("Error cleaning up channel service")

        try:
            from src.services.websocket_service.manager import (
                websocket_manager as _ws_mgr,
            )

            await _ws_mgr.close_all()
        except Exception:
            logger.exception("Error closing WebSocket connections")

        try:
            from src.services.service_manager import (
                get_mongo_client,
                reset_mongo_client,
            )

            mongo = get_mongo_client()
            if mongo is not None:
                mongo.close()
                reset_mongo_client()
                logger.info("MongoDB client closed")
        except Exception:
            logger.exception("Error closing MongoDB client")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifespan events."""
        sweep_service, proactive_service = await _startup()
        yield
        await _shutdown(sweep_service, proactive_service)

    # Create FastAPI application instance
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered desktop companion backend with vision, speech, and memory capabilities",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure middlewares
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)
    return app


# Global app instance (initialized on first import or when config is loaded)
app = None

DEFAULT_YAML_FILE = "yaml_files/main.yml"


def get_app():
    """Get or create the FastAPI application instance.

    Self-sufficient factory for uvicorn string import:
      uvicorn "src.main:get_app" --factory --reload
      uvicorn "src.main:get_app" --factory --workers 4

    Reads YAML_FILE env var (default: yaml_files/main.yml) for config path.
    """
    global app
    if app is None:
        yaml_file = os.getenv("YAML_FILE", DEFAULT_YAML_FILE)
        config_paths = load_main_config(yaml_file)
        app = create_app(config_paths)
    return app


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="DesktopMate+ Backend Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Use default config (yaml_files/main.yml)
  uv run src/main.py

  # Override port
  uv run src/main.py --port 6000

  # Override host and port
  uv run src/main.py --host 0.0.0.0 --port 6000

  # Enable auto-reload for development
  uv run src/main.py --reload

  # Use custom config file
  uv run src/main.py --yaml_file custom_config.yml

  # Combine multiple options
  uv run src/main.py --yaml_file yaml_files/main.yml --port 6000 --reload
        """,
    )
    parser.add_argument(
        "--yaml_file",
        type=str,
        default="yaml_files/main.yml",
        help="Path to main YAML configuration file (default: yaml_files/main.yml)",
    )
    parser.add_argument(
        "--host", type=str, default=None, help="Server host (overrides YAML config)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Server port (overrides YAML config)"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    # Load main configuration
    try:
        config_paths = load_main_config(args.yaml_file)
        logger.info(f"✅ Loaded configuration from: {args.yaml_file}")
    except Exception:
        logger.exception(f"⚠️  Failed to load configuration from {args.yaml_file}")
        exit(1)

    # Export YAML_FILE so get_app() factory can pick it up on (re)import
    os.environ["YAML_FILE"] = args.yaml_file

    # Get settings after initialization
    settings = get_settings()

    # Determine server settings
    host = args.host or settings.host
    port = args.port or settings.port
    reload = args.reload or settings.debug

    # Run the server via string import + factory so --reload and --workers work correctly
    uvicorn.run(
        "src.main:get_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if settings.debug else "info",
    )
