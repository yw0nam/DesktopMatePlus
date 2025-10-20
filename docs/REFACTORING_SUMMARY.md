# Service Initialization Refactoring - Summary

## Overview

Refactored the service initialization system to be more readable, maintainable, and secure.

## Key Changes

### 1. Removed `__init__` Based Initialization

**Before:**
```python
# src/services/__init__.py
class _TTSService:
    tts_engine = None

class _VLMService:
    vlm_engine = None

_tts_service = _TTSService()
_vlm_service = _VLMService()
```

**After:**
```python
# src/services/__init__.py
from src.services.service_manager import (
    get_tts_service,
    get_vlm_service,
    initialize_services,
)
```

### 2. Centralized Service Manager

Created `src/services/service_manager.py` with:
- `initialize_services()` - Initialize all services
- `initialize_tts_service(config_path)` - Initialize TTS
- `initialize_vlm_service(config_path)` - Initialize VLM
- `get_tts_service()` - Get TTS service instance
- `get_vlm_service()` - Get VLM service instance

### 3. YAML-Based Configuration

**Structure:**
```
yaml_files/
├── main.yml                          # Service registry
└── services/
    ├── tts_service/
    │   └── fish_speech.yml
    ├── vlm_service/
    │   └── openai_compatible.yml
    └── agent_service/
        └── openai_compatible.yml
```

**YAML Format with `type` and `configs`:**
```yaml
tts_config:
  type: "fish_local_tts"              # Service type for factory
  configs:                             # Passed as **kwargs
    base_url: "http://localhost:8080/v1/tts"
    temperature: 0.7
    # ... other configs
```

### 4. Environment-Based API Keys

API keys are loaded from `.env` file, not stored in YAML:

```bash
# .env
VLM_API_KEY=your-key
VLM_BASE_URL=http://localhost:8001
VLM_MODEL_NAME=chat_model
TTS_API_KEY=your-key
TTS_BASE_URL=http://localhost:8080
```

### 5. Command-Line Configuration

```bash
# Run with custom YAML config
uv run src/main.py --yaml_file yaml_files/main.yml

# With additional options
uv run src/main.py --yaml_file yaml_files/main.yml --host 0.0.0.0 --port 8800 --reload
```

## Files Changed

### Created:
1. `src/services/service_manager.py` - Service initialization logic
2. `yaml_files/main.yml` - Main service registry
3. `yaml_files/services/tts_service/fish_speech.yml` - TTS config
4. `yaml_files/services/vlm_service/openai_compatible.yml` - VLM config
5. `docs/service_initialization_guide.md` - Full documentation
6. `docs/SERVICE_INITIALIZATION_QUICKSTART.md` - Quick reference
7. `examples/test_service_init.py` - Test script

### Modified:
1. `src/services/__init__.py` - Exports from service_manager
2. `src/main.py` - Added CLI args and YAML loading
3. `src/api/routes/tts.py` - Use `get_tts_service()`
4. `src/api/routes/vlm.py` - Use `get_vlm_service()`
5. `src/services/health.py` - Use getter functions
6. `.env.example` - Added TTS_API_KEY
7. `pyproject.toml` - Added pyyaml dependency

## Usage Examples

### Running the Server

```bash
# Standard run
uv run src/main.py --yaml_file yaml_files/main.yml

# Development with reload
uv run src/main.py --yaml_file yaml_files/main.yml --reload

# Custom host/port
uv run src/main.py --yaml_file yaml_files/main.yml --host 0.0.0.0 --port 8800
```

### In Code

```python
from src.services import get_tts_service, get_vlm_service

# Get service instances (initialized at startup)
tts = get_tts_service()
vlm = get_vlm_service()

# Use services
audio = tts.generate_speech("Hello world")
description = vlm.generate_response(image_data, "Describe this")
```

## Benefits

1. ✅ **Readable** - Clear initialization, no hidden `__init__` magic
2. ✅ **Secure** - API keys in `.env`, not in code or YAML
3. ✅ **Flexible** - Easy to switch providers via YAML `type` field
4. ✅ **Maintainable** - Centralized service management
5. ✅ **Type-Safe** - Factory pattern with proper types
6. ✅ **Testable** - Easy to mock or inject configs
7. ✅ **Configurable** - CLI args for runtime configuration

## Migration Guide

### For API Routes

**Before:**
```python
from src.services import _tts_service

if _tts_service.tts_engine is None:
    raise HTTPException(...)

audio = _tts_service.tts_engine.generate_speech(text)
```

**After:**
```python
from src.services import get_tts_service

tts_service = get_tts_service()
if tts_service is None:
    raise HTTPException(...)

audio = tts_service.generate_speech(text)
```

### For Service Initialization

**Before:**
```python
# In main.py lifespan
from src.services import _tts_service
from src.services.tts_service.tts_factory import TTSFactory

tts_engine = TTSFactory.get_tts_engine("fish_local_tts", base_url=url)
_tts_service.tts_engine = tts_engine
```

**After:**
```python
# In main.py lifespan
from src.services import initialize_services

# All services initialized from YAML configs
initialize_services()
```

## Testing

Run the test script to verify initialization:
```bash
uv run examples/test_service_init.py
```

## Next Steps

1. ✅ TTS and VLM services refactored
2. 🔜 Agent service initialization (TODO)
3. 🔜 Add more service providers via YAML configs
4. 🔜 Add integration tests

## References

- Full documentation: `docs/service_initialization_guide.md`
- Quick start: `docs/SERVICE_INITIALIZATION_QUICKSTART.md`
- Main config: `yaml_files/main.yml`
- Service manager: `src/services/service_manager.py`
