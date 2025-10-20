# Service Initialization Guide

## Overview

The DesktopMate+ backend uses a **centralized service initialization system** that loads configurations from YAML files and manages service instances as singletons. This approach provides:

- ✅ Clear separation between configuration and code
- ✅ Easy-to-read service setup
- ✅ Type-based service selection (pluggable architecture)
- ✅ Secure credential management via `.env` files
- ✅ Centralized service access via getter functions

## Architecture

### Key Components

1. **YAML Configuration Files** (`yaml_files/services/`)
   - Define service types and configurations
   - Keep settings separate from code
   - Easy to modify without code changes

2. **Service Manager** (`src/services/service_manager.py`)
   - Loads YAML configurations
   - Initializes services using factories
   - Manages service lifecycle
   - Provides getter functions for service access

3. **Environment Variables** (`.env` file)
   - Store sensitive credentials (API keys)
   - Override YAML configurations
   - Not committed to version control

4. **Service Factories**
   - TTS Factory: Creates TTS service instances
   - VLM Factory: Creates VLM service instances
   - Support multiple providers (pluggable)

## Configuration Structure

### TTS Service YAML (`yaml_files/services/tts_service/fish_speech.yml`)

```yaml
tts_config:
  type: "fish_local_tts"  # Service type for factory
  configs:
    base_url: "http://localhost:8080/v1/tts"
    # api_key loaded from TTS_API_KEY env var
    format: "wav"
    seed: null
    streaming: false
    use_memory_cache: "off"
    chunk_length: 200
    max_new_tokens: 1024
    top_p: 0.7
    repetition_penalty: 1.2
    temperature: 0.7
```

**Key Points:**
- `type`: Determines which factory method to use
- `configs`: Dictionary passed as `**kwargs` to factory
- API keys loaded from environment variables (not in YAML)

### VLM Service YAML (`yaml_files/services/vlm_service/openai_compatible.yml`)

```yaml
vlm_config:
  type: "openai"  # Service type for factory
  configs:
    # API credentials from env vars:
    # - VLM_API_KEY
    # - VLM_BASE_URL
    # - VLM_MODEL_NAME
    temperature: 0.7
    top_p: 0.9
    max_tokens: 2048
```

## Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```env
# TTS Service
TTS_BASE_URL=http://localhost:8080/v1/tts
# TTS_API_KEY=your_key_here  # Optional

# VLM Service
VLM_BASE_URL=http://localhost:8001
VLM_MODEL_NAME=chat_model
# VLM_API_KEY=your_key_here  # Optional for local servers
```

**Environment variables override YAML configurations.**

## Usage

### 1. Initialize Services (in `main.py`)

```python
from src.services import initialize_services

# Initialize all services from YAML configs
initialize_services()
```

This loads configurations, reads environment variables, and creates service instances.

### 2. Access Services in API Routes

```python
from src.services import get_tts_service, get_vlm_service

# In your route handler
tts_service = get_tts_service()
if tts_service is None:
    raise HTTPException(503, "TTS service not initialized")

audio = tts_service.generate_speech(text="Hello")
```

### 3. Run with uv

```bash
# Install dependencies
uv pip install -r requirements.txt

# Run the application
uv run python -m src.main

# Or run tests
uv run python examples/test_service_init.py
```

## Service Initialization Flow

```
1. Application Startup
   ↓
2. Load YAML Configuration
   ↓
3. Read Environment Variables (.env)
   ↓
4. Merge Configs (env vars override YAML)
   ↓
5. Call Factory with type + **configs
   ↓
6. Create Service Instance
   ↓
7. Perform Health Check
   ↓
8. Store as Singleton
   ↓
9. Access via get_xxx_service()
```

## Adding New Services

### 1. Create YAML Configuration

```yaml
# yaml_files/services/new_service/config.yml
service_config:
  type: "provider_name"
  configs:
    param1: value1
    param2: value2
```

### 2. Add Initialization Function

```python
# In src/services/service_manager.py

def initialize_new_service(
    config_path: Optional[str | Path] = None,
    force_reinit: bool = False
) -> NewService:
    global _new_service_instance

    if _new_service_instance is not None and not force_reinit:
        return _new_service_instance

    # Load config
    config = _load_yaml_config(config_path)
    service_config = config.get("service_config", {})

    service_type = service_config.get("type")
    service_configs = service_config.get("configs", {})

    # Override with env vars
    # ... add env var logic ...

    # Create service
    service = ServiceFactory.get_service(service_type, **service_configs)

    _new_service_instance = service
    return service
```

### 3. Add Getter Function

```python
def get_new_service() -> Optional[NewService]:
    return _new_service_instance
```

### 4. Export in `__init__.py`

```python
from src.services.service_manager import get_new_service

__all__ = [
    # ... existing exports ...
    "get_new_service",
]
```

## Benefits

1. **Readability**: Service setup is clear and declarative
2. **Maintainability**: Configurations are separate from code
3. **Security**: API keys in `.env`, not in code or YAML
4. **Flexibility**: Easy to switch providers by changing `type`
5. **Testing**: Can initialize with different configs for tests
6. **Deployment**: Different configs per environment (dev/prod)

## Migration from Old System

### Old Way (❌ Ambiguous)
```python
# In main.py - scattered initialization
from src.services import _tts_service
tts_engine = TTSFactory.get_tts_engine("fish_local_tts", base_url=...)
_tts_service.tts_engine = tts_engine

# In routes - unclear service access
from src.services import _tts_service
audio = _tts_service.tts_engine.generate_speech(...)
```

### New Way (✅ Clean)
```python
# In main.py - one line initialization
from src.services import initialize_services
initialize_services()

# In routes - clear service access
from src.services import get_tts_service
tts_service = get_tts_service()
audio = tts_service.generate_speech(...)
```

## Troubleshooting

### Service Not Initialized
- Check YAML file exists and is valid
- Verify environment variables are set
- Check logs for initialization errors

### API Key Errors
- Ensure `.env` file exists
- Set `VLM_API_KEY` or `TTS_API_KEY` in `.env`
- For local servers, default "dummy-key" is used

### Import Errors
- Use getter functions: `get_tts_service()`, not `_tts_service`
- Import from `src.services`, not `src.services.service_manager`

## Testing

```bash
# Test service initialization
uv run python examples/test_service_init.py

# Run API tests
uv run pytest tests/test_tts_api_integration.py
uv run pytest tests/test_vlm_api_integration.py
```

## Summary

The new service initialization system provides:
- 🎯 **Single initialization point**: `initialize_services()`
- 📄 **YAML-based configuration**: Easy to read and modify
- 🔐 **Secure credentials**: API keys in `.env` files
- 🔌 **Pluggable architecture**: Change `type` to switch providers
- 🎨 **Clean code**: Getter functions for service access
- ✅ **Easy testing**: Mock or override services as needed
