"""FastAPI application entry point."""

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path

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

    # Resolve service config paths relative to main.yml location
    base_dir = yaml_path.parent
    services = config.get("services", {})

    resolved_paths = {}
    for service_name, config_file in services.items():
        if config_file:
            service_path = base_dir / "services" / service_name / config_file
            resolved_paths[f"{service_name}_path"] = service_path

    return resolved_paths


def create_app(config_paths: dict | None = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        config_paths: Dictionary of service config paths. Captured by lifespan closure.
    """
    if config_paths is None:
        config_paths = {}

    settings = get_settings()

    async def _startup() -> "BackgroundSweepService | None":
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_retention = os.getenv("LOG_RETENTION", "30 days")
        setup_logging(level=log_level, retention=log_retention)

        print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
        print(f"📝 API Documentation: http://{settings.host}:{settings.port}/docs")
        print(f"🔧 Debug mode: {settings.debug}")
        print(f"📊 Log level: {log_level} | Retention: {log_retention}")

        sweep_service: BackgroundSweepService | None = None

        try:
            from src.services import (
                get_agent_service,
                initialize_agent_service,
                initialize_emotion_motion_mapper,
                initialize_ltm_service,
                initialize_mongodb_client,
                initialize_tts_service,
            )

            print("\n📋 Loading service configurations...")

            if config_paths.get("tts_config_path"):
                print(f"  - TTS config: {config_paths['tts_config_path']}")
                initialize_tts_service(config_path=config_paths["tts_config_path"])
            else:
                print("  - TTS config: Using default")
                initialize_tts_service()

            initialize_emotion_motion_mapper()

            # MongoDB client for checkpointer + session_registry (before agent)
            if config_paths.get("checkpointer_config_path"):
                initialize_mongodb_client(
                    config_path=config_paths["checkpointer_config_path"]
                )
            else:
                initialize_mongodb_client()

            if config_paths.get("agent_config_path"):
                print(f"  - Agent config: {config_paths['agent_config_path']}")
                initialize_agent_service(
                    config_path=config_paths["agent_config_path"],
                )
            else:
                print("  - Agent config: Using default")
                initialize_agent_service()

            if config_paths.get("ltm_config_path"):
                print(f"  - LTM config: {config_paths['ltm_config_path']}")
                initialize_ltm_service(config_path=config_paths["ltm_config_path"])
            else:
                print("  - LTM config: Using default")
                initialize_ltm_service()

            # Async initialization: MCP tools + agent creation
            agent_svc = get_agent_service()
            if agent_svc is not None:
                await agent_svc.initialize_async()
                logger.info("Agent async initialization complete")

            # Channel service (Slack 등 외부 채널)
            try:
                import yaml as _yaml

                from src.services.channel_service import init_channel_service
                from src.services.channel_service.slack_service import SlackSettings

                channel_config_path = config_paths.get("channel_service_path")
                slack_settings = SlackSettings()
                if channel_config_path and Path(channel_config_path).exists():
                    with open(channel_config_path, encoding="utf-8") as _f:
                        _raw = _yaml.safe_load(_f) or {}
                    import os as _os

                    slack_cfg_dict = _raw.get("slack", {})
                    # env var fallback for credentials not set in YAML
                    if not slack_cfg_dict.get("bot_token"):
                        slack_cfg_dict["bot_token"] = _os.getenv("SLACK_BOT_TOKEN", "")
                    if not slack_cfg_dict.get("signing_secret"):
                        slack_cfg_dict["signing_secret"] = _os.getenv(
                            "SLACK_SIGNING_SECRET", ""
                        )

                    slack_settings = SlackSettings(**slack_cfg_dict)
                await init_channel_service(slack_settings)
                logger.info("Channel service initialized")
            except Exception:
                logger.exception("Failed to initialize channel service")

            try:
                import yaml as _yaml

                from src.services.task_sweep_service import (
                    BackgroundSweepService,
                    SweepConfig,
                )

                sweep_config_path = config_paths.get("task_sweep_service_path")
                sweep_cfg_dict: dict = {}
                if sweep_config_path and Path(sweep_config_path).exists():
                    with open(sweep_config_path, encoding="utf-8") as _f:
                        _raw = _yaml.safe_load(_f) or {}
                    sweep_cfg_dict = _raw.get("sweep_config", {})
                sweep_cfg = SweepConfig(**sweep_cfg_dict)

                from src.services.channel_service import get_slack_service
                from src.services.service_manager import get_session_registry

                registry = get_session_registry()
                agent_for_sweep = get_agent_service()
                if registry is not None and agent_for_sweep is not None:
                    sweep_service = BackgroundSweepService(
                        agent_service=agent_for_sweep,
                        session_registry=registry,
                        config=sweep_cfg,
                        slack_service_fn=get_slack_service,
                    )
                    await sweep_service.start()
                    logger.info(
                        f"Task sweep started "
                        f"(interval={sweep_cfg.sweep_interval_seconds}s, "
                        f"ttl={sweep_cfg.task_ttl_seconds}s)"
                    )
                else:
                    logger.warning(
                        "Task sweep skipped: agent or session registry not available"
                    )
            except Exception:
                logger.exception("Failed to start background sweep service")

        except Exception as e:
            print(f"⚠️  Failed to initialize services: {e}")
            import traceback

            traceback.print_exc()

        return sweep_service

    async def _shutdown(
        sweep_service: "BackgroundSweepService | None",
    ) -> None:
        if sweep_service is not None:
            await sweep_service.stop()
        print(f"👋 Shutting down {settings.app_name}")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifespan events."""
        sweep_service = await _startup()
        yield
        await _shutdown(sweep_service)

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
        print(f"✅ Loaded configuration from: {args.yaml_file}")
    except Exception as e:
        print(f"⚠️  Failed to load configuration from {args.yaml_file}: {e}")
        import traceback

        traceback.print_exc()
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
