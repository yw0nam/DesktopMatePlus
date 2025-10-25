"""FastAPI application entry point."""

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router as api_router
from src.configs.settings import settings

# Store config paths globally for lifespan to access
_config_paths = {
    "tts_config_path": None,
    "vlm_config_path": None,
    "agent_config_path": None,
}


def load_main_config(yaml_file: str | Path) -> dict:
    """Load main configuration file that references service configs.

    Args:
        yaml_file: Path to main.yml configuration file

    Returns:
        Dictionary with service configuration paths
    """
    yaml_path = Path(yaml_file)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

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
    # Startup
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📝 API Documentation: http://{settings.host}:{settings.port}/docs")
    print(f"🔧 Debug mode: {settings.debug}")

    # Initialize all services using the centralized service manager
    try:
        from src.services import (
            initialize_agent_service,
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

    except Exception as e:
        print(f"⚠️  Failed to initialize services: {e}")
        import traceback

        traceback.print_exc()

    yield

    # Shutdown
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

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="DesktopMate+ Backend Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python -m src.main
  python -m src.main --yaml_file yaml_files/main.yml
  uv run src/main.py --yaml_file yaml_files/main.yml

Environment variables (.env file):
  - VLM_API_KEY: API key for VLM service
  - VLM_BASE_URL: Base URL for VLM service
  - VLM_MODEL_NAME: Model name for VLM service
  - TTS_API_KEY: API key for TTS service (optional)
  - TTS_BASE_URL: Base URL for TTS service
        """,
    )
    parser.add_argument(
        "--yaml_file",
        type=str,
        default="yaml_files/main.yml",
        help="Path to main YAML configuration file (default: yaml_files/main.yml)",
    )
    parser.add_argument(
        "--host", type=str, default=None, help=f"Server host (default: {settings.host})"
    )
    parser.add_argument(
        "--port", type=int, default=None, help=f"Server port (default: {settings.port})"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    # Load main configuration if provided
    if args.yaml_file:
        try:
            config_paths = load_main_config(args.yaml_file)
            _config_paths.update(config_paths)
            print(f"✅ Loaded configuration from: {args.yaml_file}")
        except Exception as e:
            print(f"⚠️  Failed to load configuration from {args.yaml_file}: {e}")
            print("   Using default configuration paths")

    # Determine server settings
    host = args.host or settings.host
    port = args.port or settings.port
    reload = args.reload or settings.debug

    # Run the server
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if settings.debug else "info",
    )
