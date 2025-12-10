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
from fastapi.staticfiles import StaticFiles

from src.api.routes import router as api_router
from src.configs.settings import get_settings, initialize_settings
from src.core.logger import setup_logging
from src.core.middleware import RequestIDMiddleware

load_dotenv()
# Store config paths globally for lifespan to access
_config_paths = {
    "tts_config_path": None,
    "vlm_config_path": None,
    "agent_config_path": None,
    "stm_config_path": None,
    "ltm_config_path": None,
}


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Setup logging first
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_retention = os.getenv("LOG_RETENTION", "30 days")
    setup_logging(level=log_level, retention=log_retention)

    # Get settings instance
    settings = get_settings()

    # Startup
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📝 API Documentation: http://{settings.host}:{settings.port}/docs")
    print(f"🔧 Debug mode: {settings.debug}")
    print(f"📊 Log level: {log_level} | Retention: {log_retention}")

    # Initialize all services using the centralized service manager
    try:
        from src.services import (
            initialize_agent_service,
            initialize_ltm_service,
            initialize_stm_service,
            initialize_tts_service,
            initialize_vlm_service,
        )

        # Initialize services from YAML configurations
        # API keys are loaded from environment variables (.env file)
        print("\n📋 Loading service configurations...")

        # Initialize TTS service
        if _config_paths.get("tts_config_path"):
            print(f"  - TTS config: {_config_paths['tts_config_path']}")
            initialize_tts_service(config_path=_config_paths["tts_config_path"])
        else:
            print("  - TTS config: Using default")
            initialize_tts_service()

        # Initialize VLM service
        if _config_paths.get("vlm_config_path"):
            print(f"  - VLM config: {_config_paths['vlm_config_path']}")
            initialize_vlm_service(config_path=_config_paths["vlm_config_path"])
        else:
            print("  - VLM config: Using default")
            initialize_vlm_service()

        # Initialize Agent service
        if _config_paths.get("agent_config_path"):
            print(f"  - Agent config: {_config_paths['agent_config_path']}")
            initialize_agent_service(config_path=_config_paths["agent_config_path"])
        else:
            print("  - Agent config: Using default")
            initialize_agent_service()

        if _config_paths.get("stm_config_path"):
            print(f"  - STM config: {_config_paths['stm_config_path']}")
            initialize_stm_service(config_path=_config_paths["stm_config_path"])
        else:
            print("  - STM config: Using default from settings")
            initialize_stm_service()

        # Initialize LTM service (no client API exposure needed)
        if _config_paths.get("ltm_config_path"):
            print(f"  - LTM config: {_config_paths['ltm_config_path']}")
            initialize_ltm_service(config_path=_config_paths["ltm_config_path"])
        else:
            print("  - LTM config: Using default")
            initialize_ltm_service()

    except Exception as e:
        print(f"⚠️  Failed to initialize services: {e}")
        import traceback

        traceback.print_exc()

    yield

    # Shutdown
    print(f"👋 Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    This function must be called after settings are initialized.
    """
    settings = get_settings()

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
    # Add Request ID middleware first (executes last in the chain)
    app.add_middleware(RequestIDMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)

    # Mount static asset directories so the frontend can fetch backgrounds and Live2D models
    project_root = Path(__file__).resolve().parent.parent
    backgrounds_dir = project_root / "resources" / "backgrounds"
    live2d_dir = project_root / "resources" / "live2d-models"
    # image_dir = project_root / "static"

    if backgrounds_dir.exists():
        print(f"📁 Serving backgrounds from {backgrounds_dir}")
        app.mount(
            "/v1/bg",
            StaticFiles(directory=str(backgrounds_dir)),
            name="backgrounds",
        )
    else:
        print(f"⚠️ Backgrounds directory not found: {backgrounds_dir}")

    if live2d_dir.exists():
        print(f"📁 Serving Live2D models from {live2d_dir}")
        app.mount(
            "/v1/live2d",
            StaticFiles(directory=str(live2d_dir)),
            name="live2d-models",
        )
    else:
        print(f"⚠️ Live2D directory not found: {live2d_dir}")

    # if image_dir.exists():
    #     print(f"📁 Serving static images from {image_dir}")
    #     app.mount(
    #         "/v1/static",
    #         StaticFiles(directory=str(image_dir)),
    #         name="static-images",
    #     )
    # else:
    #     print(f"⚠️ Static images directory not found: {image_dir}")

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
            # Try to get settings (will raise if not initialized)
            get_settings()
            app = create_app()
        except RuntimeError:
            # Settings not initialized yet, return None
            # This will be properly initialized when main() runs
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
        _config_paths.update(config_paths)
        print(f"✅ Loaded configuration from: {args.yaml_file}")
    except Exception as e:
        print(f"⚠️  Failed to load configuration from {args.yaml_file}: {e}")
        import traceback

        traceback.print_exc()
        exit(1)

    # Get settings after initialization
    settings = get_settings()

    # Create app after settings are initialized
    app = create_app()

    # Determine server settings
    host = args.host or settings.host
    port = args.port or settings.port
    reload = args.reload or settings.debug

    # Run the server
    # Note: We pass the app instance directly to avoid reload issues
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if settings.debug else "info",
    )
