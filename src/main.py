"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router as api_router
from src.configs.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📝 API Documentation: http://{settings.host}:{settings.port}/docs")
    print(f"🔧 Debug mode: {settings.debug}")

    # Initialize TTS service
    try:
        from src.services import _tts_service
        from src.services.tts_service.tts_factory import TTSFactory

        # Create TTS engine using factory
        tts_engine = TTSFactory.get_tts_engine(
            "fish_local_tts", base_url=settings.tts_base_url.rstrip("/") + "/v1/tts"
        )

        # Store in global service variable
        _tts_service.tts_engine = tts_engine

        print(
            f"✅ TTS service initialized with Fish Speech URL: {settings.tts_base_url}"
        )
    except Exception as e:
        print(f"⚠️  Failed to initialize TTS service: {e}")

    # Initialize VLM service
    try:
        from src.services import _vlm_service
        from src.services.vlm_service.vlm_factory import VLMFactory

        # Create VLM engine using factory
        vlm_engine = VLMFactory.get_vlm_service(
            "openai",
            openai_api_key=settings.vlm_api_key,
            openai_api_base=settings.vlm_base_url,
            model_name=settings.vlm_model_name,
        )

        # Store in global service variable
        _vlm_service.vlm_engine = vlm_engine

        print(f"✅ VLM service initialized with model: {settings.vlm_model_name}")
    except Exception as e:
        print(f"⚠️  Failed to initialize VLM service: {e}")

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
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
