# Service Initialization Guide

This guide explains the new service initialization system that uses YAML configuration files and environment variables.

## Overview

The service initialization system has been refactored to:
- Use YAML files for service configuration
- Load API keys from `.env` file (not exposed in YAML files)
- Support flexible service types via factory pattern
- Enable easy configuration through command-line arguments

## Architecture

```
yaml_files/
├── main.yml                          # Main configuration (service registry)
└── services/
    ├── tts_service/
    │   └── fish_speech.yml          # TTS configuration
    ├── vlm_service/
    │   └── openai_compatible.yml    # VLM configuration
    └── agent_service/
        └── openai_compatible.yml    # Agent configuration (TODO)
```

## Configuration Structure

### Main Configuration (`yaml_files/main.yml`)

```yaml
services:
  vlm_service: openai_compatible.yml
  tts_service: fish_speech.yml
  agent_service: openai_compatible.yml
```

This file maps service names to their configuration files.

### Service Configuration Files

Each service configuration follows this pattern:

```yaml
<service>_config:
  type: "<provider_type>"        # Service type for factory pattern
  configs:                        # Configuration passed as **kwargs
    temperature: 0.7
    top_p: 0.9
    # ... other provider-specific configs
```

**Example - TTS Service (`fish_speech.yml`):**

```yaml
tts_config:
  type: "fish_local_tts"
  configs:
    base_url: "http://localhost:8080/v1/tts"
    format: "wav"
    temperature: 0.7
    # ... other configs
```

**Example - VLM Service (`openai_compatible.yml`):**

```yaml
vlm_config:
  type: "openai"
  configs:
    temperature: 0.7
    top_p: 0.9
    max_tokens: 2048
```

## Environment Variables

API keys and sensitive information are loaded from `.env` file:

```bash
# VLM Service
VLM_API_KEY=your-api-key
VLM_BASE_URL=http://localhost:8001
VLM_MODEL_NAME=chat_model

# TTS Service
TTS_API_KEY=your-api-key
TTS_BASE_URL=http://localhost:8080

# LLM Service (for agent)
LLM_API_KEY=your-api-key
LLM_BASE_URL=http://localhost:55120/v1
LLM_MODEL=chat_model
```

## Usage

### Running the Server

**Using UV (recommended):**
```bash
uv run src/main.py --yaml_file yaml_files/main.yml
```

**Using Python:**
```bash
python -m src.main --yaml_file yaml_files/main.yml
```

**With custom host/port:**
```bash
uv run src/main.py --yaml_file yaml_files/main.yml --host 0.0.0.0 --port 8800
```

**With auto-reload:**
```bash
uv run src/main.py --yaml_file yaml_files/main.yml --reload
```

### Programmatic Usage

```python
from src.services import initialize_services, get_tts_service, get_vlm_service

# Initialize all services (loads from default YAML files)
initialize_services()

# Or initialize individual services with custom config paths
from src.services import initialize_tts_service, initialize_vlm_service

tts_service = initialize_tts_service(
    config_path="yaml_files/services/tts_service/fish_speech.yml"
)

vlm_service = initialize_vlm_service(
    config_path="yaml_files/services/vlm_service/openai_compatible.yml"
)

# Get service instances anywhere in the code
tts = get_tts_service()
vlm = get_vlm_service()

# Use services
audio_data = tts.generate_speech("Hello world")
description = vlm.generate_response(image_data, "Describe this image")
```

## Service Manager API

The `src/services/service_manager.py` module provides the following functions:

### `initialize_services(tts_config_path=None, vlm_config_path=None, force_reinit=False)`

Initialize all services from YAML configurations.

**Args:**
- `tts_config_path`: Path to TTS YAML config (optional, uses default if None)
- `vlm_config_path`: Path to VLM YAML config (optional, uses default if None)
- `force_reinit`: Reinitialize even if already initialized

**Returns:** Tuple of (tts_service, vlm_service)

### `initialize_tts_service(config_path=None, force_reinit=False)`

Initialize only TTS service.

### `initialize_vlm_service(config_path=None, force_reinit=False)`

Initialize only VLM service.

### `get_tts_service() -> Optional[TTSService]`

Get the initialized TTS service instance (or None if not initialized).

### `get_vlm_service() -> Optional[VLMService]`

Get the initialized VLM service instance (or None if not initialized).

## Adding New Service Types

To add a new service provider:

1. **Implement the service class:**
   ```python
   # src/services/tts_service/new_provider.py
   from src.services.tts_service.service import TTSService

   class NewProviderTTS(TTSService):
       def __init__(self, api_key: str, **configs):
           self.api_key = api_key
           # ... initialize with configs

       def generate_speech(self, text: str, **kwargs):
           # ... implementation
           pass

       def is_healthy(self):
           # ... implementation
           pass
   ```

2. **Update the factory:**
   ```python
   # src/services/tts_service/tts_factory.py
   @staticmethod
   def get_tts_engine(service_type: str, **configs) -> TTSService:
       if service_type == "fish_local_tts":
           return FishSpeechTTS(**configs)
       elif service_type == "new_provider":
           return NewProviderTTS(**configs)
       else:
           raise ValueError(f"Unknown TTS service type: {service_type}")
   ```

3. **Create YAML configuration:**
   ```yaml
   # yaml_files/services/tts_service/new_provider.yml
   tts_config:
     type: "new_provider"
     configs:
       custom_param: "value"
       temperature: 0.7
   ```

4. **Update main.yml:**
   ```yaml
   services:
     tts_service: new_provider.yml  # Changed from fish_speech.yml
   ```

## Benefits

1. **Clean Separation:** API keys are never in YAML files, only in `.env`
2. **Flexible Configuration:** Easy to switch between providers by changing YAML files
3. **Type Safety:** Factory pattern with type hints ensures correct service types
4. **Testability:** Easy to mock services or use different configs for testing
5. **Readability:** Clear service initialization in one place
6. **No `__init__` Magic:** Services are explicitly initialized, not created in `__init__.py`

## Migration from Old System

**Old way (deprecated):**
```python
from src.services import _tts_service, _vlm_service

# Services were initialized in __init__.py with global instances
audio = _tts_service.tts_engine.generate_speech("Hello")
```

**New way:**
```python
from src.services import get_tts_service, get_vlm_service

# Services are initialized via service_manager with YAML configs
tts_service = get_tts_service()
audio = tts_service.generate_speech("Hello")
```

## Troubleshooting

### Service not initialized error

Make sure services are initialized before use:
```python
from src.services import initialize_services

# Call this at startup (already done in main.py lifespan)
initialize_services()
```

### Configuration file not found

Check that YAML files exist in the correct locations:
```bash
ls -la yaml_files/main.yml
ls -la yaml_files/services/tts_service/fish_speech.yml
ls -la yaml_files/services/vlm_service/openai_compatible.yml
```

### API key not loaded

Check `.env` file exists and contains the required variables:
```bash
cat .env | grep -E "VLM_API_KEY|TTS_API_KEY|LLM_API_KEY"
```

Make sure `python-dotenv` loads the file (already done in `settings.py`).

### Service health check fails

Check that the external services are running:
```bash
# Check VLM service
curl http://localhost:8001/health

# Check TTS service
curl http://localhost:8080/health
```
