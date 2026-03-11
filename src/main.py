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
    with open(yaml_path, "r", encoding="utf-8") as f:
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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifespan events."""
        # Setup logging first
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_retention = os.getenv("LOG_RETENTION", "30 days")
        setup_logging(level=log_level, retention=log_retention)

        # Startup
        print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
        print(f"📝 API Documentation: http://{settings.host}:{settings.port}/docs")
        print(f"🔧 Debug mode: {settings.debug}")
        print(f"📊 Log level: {log_level} | Retention: {log_retention}")

        sweep_service: "BackgroundSweepService | None" = None  # noqa: F821

        # Initialize all services using the centralized service manager
        try:
            from src.services import (
                get_stm_service,
                initialize_agent_service,
                initialize_ltm_service,
                initialize_stm_service,
                initialize_tts_service,
            )

            print("\n📋 Loading service configurations...")

            # Initialize TTS service
            if config_paths.get("tts_config_path"):
                print(f"  - TTS config: {config_paths['tts_config_path']}")
                initialize_tts_service(config_path=config_paths["tts_config_path"])
            else:
                print("  - TTS config: Using default")
                initialize_tts_service()

            # Initialize Agent service
            if config_paths.get("agent_config_path"):
                print(f"  - Agent config: {config_paths['agent_config_path']}")
                initialize_agent_service(config_path=config_paths["agent_config_path"])
            else:
                print("  - Agent config: Using default")
                initialize_agent_service()

            if config_paths.get("stm_config_path"):
                print(f"  - STM config: {config_paths['stm_config_path']}")
                initialize_stm_service(config_path=config_paths["stm_config_path"])
            else:
                print("  - STM config: Using default from settings")
                initialize_stm_service()

            # Initialize LTM service (no client API exposure needed)
            if config_paths.get("ltm_config_path"):
                print(f"  - LTM config: {config_paths['ltm_config_path']}")
                initialize_ltm_service(config_path=config_paths["ltm_config_path"])
            else:
                print("  - LTM config: Using default")
                initialize_ltm_service()

            # Start background sweep service for expired delegated tasks
            try:
                import yaml as _yaml

                from src.services.task_sweep_service import (
                    BackgroundSweepService,
                    SweepConfig,
                )

                sweep_config_path = config_paths.get("task_sweep_service_path")
                sweep_cfg_dict: dict = {}
                if sweep_config_path and Path(sweep_config_path).exists():
                    with open(sweep_config_path, "r", encoding="utf-8") as _f:
                        _raw = _yaml.safe_load(_f) or {}
                    sweep_cfg_dict = _raw.get("sweep_config", {})
                sweep_cfg = SweepConfig(**sweep_cfg_dict)

                stm_svc = get_stm_service()
                if stm_svc is not None:
                    sweep_service = BackgroundSweepService(
                        stm_service=stm_svc, config=sweep_cfg
                    )
                    await sweep_service.start()
                    logger.info(
                        f"Task sweep started "
                        f"(interval={sweep_cfg.sweep_interval_seconds}s, "
                        f"ttl={sweep_cfg.task_ttl_seconds}s)"
                    )
                else:
                    logger.warning("Task sweep skipped: STM service not available")
            except Exception:
                logger.exception("Failed to start background sweep service")

        except Exception as e:
            print(f"⚠️  Failed to initialize services: {e}")
            import traceback

            traceback.print_exc()

        yield

        # Shutdown — stop sweep before other services
        if sweep_service is not None:
            await sweep_service.stop()

        print(f"👋 Shutting down {settings.app_name}")

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


def get_app():
    """Get or create the FastAPI application instance.

    This is called by uvicorn when using the string import path.
    Settings must be initialized before this is called.
    """
    global app
    if app is None:
        try:
            get_settings()
            app = create_app()
        except RuntimeError:
            pass
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

    # Get settings after initialization
    settings = get_settings()

    # Create app with config paths captured by closure
    app = create_app(config_paths)

    # Determine server settings
    host = args.host or settings.host
    port = args.port or settings.port
    reload = args.reload or settings.debug

    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if settings.debug else "info",
    )
