# DesktopMate+ Service Deployment Guide

## Architecture Overview

The DesktopMate+ backend follows a **microservices architecture** where:

1. **FastAPI Backend (Port 8000)** - Main API gateway and orchestrator
2. **VLM Service (Port 5530)** - Vision-Language Model inference server (vLLM)
3. **TTS Service (Port 8080)** - Text-to-Speech server (Fish Speech)
4. **PostgreSQL (Port 5432)** - Database for mem0 memory management (future)
5. **LLM (Port 55120)** - LLM service

```
┌─────────────────────────────────────────────────────────────┐
│                      User / Frontend                         │
│                     (Tauri Application)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ HTTP/REST API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Port 8000)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ VLM Routes   │  │ TTS Routes   │  │ Agent Logic  │      │
│  │ /v1/vlm/*    │  │ /v1/tts/*    │  │ (LangGraph)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         │ HTTP             │ HTTP             │ SQL          │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌──────────────────┐ ┌─────────────────┐ ┌──────────────┐
│  vLLM Server     │ │ Fish Speech API │ │ PostgreSQL   │
│  (Port 8001)     │ │  (Port 8080)    │ │ (Port 5432)  │
│                  │ │                 │ │              │
│ Vision-Language  │ │ Text-to-Speech  │ │ Memory Store │
│ Model Inference  │ │ Synthesis       │ │ (mem0)       │
└──────────────────┘ └─────────────────┘ └──────────────┘
```

## Deployment Options

### Option 1: Development Setup (Recommended for Development)

Run each service separately in different terminals:

#### Terminal 1: VLM Service (vLLM)
```bash
# Install vLLM (if not already installed)
pip install vllm

# Run vLLM server with a vision-language model
# Example with Qwen2-VL or similar
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2-VL-2B-Instruct \
    --port 8001 \
    --host 127.0.0.1 \
    --dtype auto \
    --max-model-len 4096

# Alternative: Use a local model
python -m vllm.entrypoints.openai.api_server \
    --model /path/to/your/vlm/model \
    --port 8001 \
    --host 127.0.0.1
```

#### Terminal 2: TTS Service (Fish Speech)
```bash
# Install Fish Speech (if not already installed)
git clone https://github.com/fishaudio/fish-speech.git
cd fish-speech
pip install -e .

# Download the model (S1-mini recommended for low resource usage)
python tools/download_model.py --model s1-mini

# Run Fish Speech API server
python -m fish_speech.api.start_http_api \
    --listen 127.0.0.1:8080 \
    --llama-checkpoint-path checkpoints/s1-mini
```

#### Terminal 3: FastAPI Backend
```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus

# Set environment variables (optional, will use defaults)
export FASTAPI_VLM_BASE_URL="http://localhost:8001"
export FASTAPI_VLM_MODEL_NAME="Qwen/Qwen2-VL-2B-Instruct"
export FASTAPI_TTS_BASE_URL="http://localhost:8080"
export FASTAPI_DEBUG=true

# Run the backend
uv run python -m src.main

# Or using uvicorn directly
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

### Option 2: Docker Compose (Recommended for Production)

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # VLM Service
  vlm:
    image: vllm/vllm-openai:latest
    ports:
      - "8001:8001"
    environment:
      - MODEL_NAME=Qwen/Qwen2-VL-2B-Instruct
      - PORT=8001
    volumes:
      - ./models:/models
      - ./cache:/root/.cache
    command: >
      --model ${MODEL_NAME}
      --port 8001
      --host 0.0.0.0
      --dtype auto
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # TTS Service
  tts:
    image: fishaudio/fish-speech:latest
    ports:
      - "8080:8080"
    volumes:
      - ./tts_models:/models
    environment:
      - MODEL_PATH=/models/s1-mini
    command: >
      python -m fish_speech.api.start_http_api
      --listen 0.0.0.0:8080
      --llama-checkpoint-path /models/s1-mini

  # PostgreSQL for mem0
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=desktopmate
      - POSTGRES_USER=desktopmate
      - POSTGRES_PASSWORD=desktopmate_secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # FastAPI Backend
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FASTAPI_VLM_BASE_URL=http://vlm:8001
      - FASTAPI_TTS_BASE_URL=http://tts:8080
      - FASTAPI_DEBUG=false
    depends_on:
      - vlm
      - tts
      - postgres
    volumes:
      - .:/app

volumes:
  postgres_data:
```

Run with:
```bash
docker-compose up
```

### Option 3: Kubernetes (Production Scale)

For production deployment at scale, use Kubernetes with separate deployments for each service.

## Environment Configuration

Create a `.env` file in the project root:

```env
# FastAPI Backend Configuration
FASTAPI_HOST=127.0.0.1
FASTAPI_PORT=8000
FASTAPI_DEBUG=false

# VLM Service Configuration
FASTAPI_VLM_BASE_URL=http://localhost:8001
FASTAPI_VLM_MODEL_NAME=Qwen/Qwen2-VL-2B-Instruct
FASTAPI_VLM_API_KEY=  # Optional, for cloud APIs

# TTS Service Configuration
FASTAPI_TTS_BASE_URL=http://localhost:8080

# Database Configuration (for future mem0 integration)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=desktopmate
POSTGRES_USER=desktopmate
POSTGRES_PASSWORD=desktopmate_secret

# Health Check Configuration
FASTAPI_HEALTH_CHECK_TIMEOUT=5
```

## Testing the Setup

### 1. Check Service Health

```bash
# Check main backend health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-10-20T...",
#   "modules": [
#     {"name": "VLM", "ready": true, "error": null},
#     {"name": "TTS", "ready": true, "error": null},
#     {"name": "Agent", "ready": true, "error": null}
#   ]
# }
```

### 2. Test VLM Service

```bash
# Test VLM directly (vLLM OpenAI-compatible API)
curl http://localhost:8001/v1/models

# Test VLM through backend
curl -X POST http://localhost:8000/v1/vlm/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "image": "https://example.com/image.jpg",
    "prompt": "Describe this image"
  }'
```

### 3. Test TTS Service

```bash
# Test TTS through backend
curl -X POST http://localhost:8000/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test.",
    "output_format": "base64"
  }'
```

## Service Startup Scripts

### `scripts/start_dev.sh`
```bash
#!/bin/bash
# Start all services for development

set -e

echo "🚀 Starting DesktopMate+ Development Environment"

# Start VLM service in background
echo "📦 Starting VLM service..."
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2-VL-2B-Instruct \
    --port 8001 \
    --host 127.0.0.1 > logs/vlm.log 2>&1 &
VLM_PID=$!

# Start TTS service in background
echo "🔊 Starting TTS service..."
python -m fish_speech.api.start_http_api \
    --listen 127.0.0.1:8080 \
    --llama-checkpoint-path checkpoints/s1-mini > logs/tts.log 2>&1 &
TTS_PID=$!

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Start FastAPI backend
echo "🌐 Starting FastAPI backend..."
uv run python -m src.main

# Cleanup on exit
trap "kill $VLM_PID $TTS_PID" EXIT
```

### `scripts/stop_dev.sh`
```bash
#!/bin/bash
# Stop all services

echo "🛑 Stopping all services..."

# Kill by port
kill $(lsof -ti:8000) 2>/dev/null || true  # FastAPI
kill $(lsof -ti:8001) 2>/dev/null || true  # VLM
kill $(lsof -ti:8080) 2>/dev/null || true  # TTS

echo "✅ All services stopped"
```

## Alternative: Cloud-Based Services

Instead of running VLM locally, you can use cloud APIs:

```env
# Use OpenAI API
FASTAPI_VLM_BASE_URL=https://api.openai.com/v1
FASTAPI_VLM_MODEL_NAME=gpt-4-vision-preview
FASTAPI_VLM_API_KEY=sk-your-openai-api-key

# Or use local vLLM
FASTAPI_VLM_BASE_URL=http://localhost:8001
FASTAPI_VLM_MODEL_NAME=Qwen/Qwen2-VL-2B-Instruct
```

The backend code automatically handles both local and cloud APIs since vLLM provides OpenAI-compatible endpoints!

## Resource Requirements

### Minimum Requirements (Development)
- **FastAPI Backend**: 512 MB RAM, 1 CPU core
- **VLM Service**: 4 GB VRAM (GPU), 8 GB RAM, 2 CPU cores
- **TTS Service**: 2 GB RAM, 2 CPU cores

### Recommended (Production)
- **FastAPI Backend**: 2 GB RAM, 2 CPU cores
- **VLM Service**: 8 GB VRAM (GPU), 16 GB RAM, 4 CPU cores
- **TTS Service**: 4 GB RAM, 4 CPU cores
- **PostgreSQL**: 2 GB RAM, 2 CPU cores

## Troubleshooting

### VLM Service Not Responding
```bash
# Check if vLLM is running
curl http://localhost:8001/health

# Check vLLM logs
tail -f logs/vlm.log

# Restart VLM service
kill $(lsof -ti:8001)
python -m vllm.entrypoints.openai.api_server --model YOUR_MODEL --port 8001
```

### TTS Service Not Responding
```bash
# Check if Fish Speech is running
curl http://localhost:8080/v1/health

# Check TTS logs
tail -f logs/tts.log

# Restart TTS service
kill $(lsof -ti:8080)
python -m fish_speech.api.start_http_api --listen 127.0.0.1:8080
```

### Backend Can't Connect to Services
```bash
# Verify services are accessible
curl http://localhost:8001/v1/models  # VLM
curl http://localhost:8080/v1/health  # TTS

# Check environment variables
env | grep FASTAPI_

# Test backend health endpoint
curl http://localhost:8000/health
```

## API Documentation

Once the backend is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Next Steps

1. **Set up all services** using one of the deployment options above
2. **Test each service individually** to ensure they work
3. **Test the integrated backend** through the health endpoint
4. **Use the API documentation** to explore available endpoints
5. **Integrate with the Tauri frontend** for the complete application
