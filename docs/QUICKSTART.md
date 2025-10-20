# Quick Start Guide

## TL;DR - Running the Services

The DesktopMate+ backend requires **3 separate services** to be running:

### 1. VLM Service (Vision-Language Model) - Port 8001
```bash
# Install vLLM
pip install vllm

# Run vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2-VL-2B-Instruct \
    --port 8001 \
    --host 127.0.0.1
```

### 2. TTS Service (Text-to-Speech) - Port 8080
```bash
# Install Fish Speech
git clone https://github.com/fishaudio/fish-speech.git
cd fish-speech
pip install -e .

# Download model
python tools/download_model.py --model s1-mini

# Run Fish Speech server
python -m fish_speech.api.start_http_api \
    --listen 127.0.0.1:8080 \
    --llama-checkpoint-path checkpoints/s1-mini
```

### 3. FastAPI Backend - Port 8000
```bash
# In the DesktopMatePlus directory
uv run python -m src.main

# Or use the service manager
chmod +x scripts/service_manager.sh
./scripts/service_manager.sh
```

## Simplified Development Setup

If you don't want to run VLM and TTS locally, you can:

1. **Mock the services** for development (backend will report services as unhealthy but won't crash)
2. **Use cloud APIs** - Configure `.env` to use OpenAI or other cloud providers

```env
# .env file for cloud-based VLM
FASTAPI_VLM_BASE_URL=https://api.openai.com/v1
FASTAPI_VLM_MODEL_NAME=gpt-4-vision-preview
FASTAPI_VLM_API_KEY=your-api-key-here
```

## Testing the Setup

```bash
# Check if all services are healthy
curl http://localhost:8000/health

# Test VLM endpoint
curl -X POST http://localhost:8000/v1/vlm/analyze \
  -H "Content-Type: application/json" \
  -d '{"image": "https://example.com/image.jpg", "prompt": "Describe this"}'

# Test TTS endpoint
curl -X POST http://localhost:8000/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "output_format": "base64"}'
```

## Architecture

```
Frontend (Tauri)
       ↓
FastAPI Backend (8000) ← YOU ARE HERE
       ↓
   ┌───┴───┐
   ↓       ↓
VLM(8001) TTS(8080)  ← External services (vLLM, Fish Speech)
```

The FastAPI backend acts as an **orchestrator** that calls external AI services. It doesn't run the AI models itself - it just coordinates between them.

## Full Documentation

See [docs/deployment_guide.md](docs/deployment_guide.md) for complete deployment options including Docker and Kubernetes.
