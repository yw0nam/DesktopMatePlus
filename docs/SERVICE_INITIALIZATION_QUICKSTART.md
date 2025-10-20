# Service Initialization - Quick Start

## Running the Server

```bash
# Using uv (recommended)
uv run src/main.py --yaml_file yaml_files/main.yml

# Or with auto-reload for development
uv run src/main.py --yaml_file yaml_files/main.yml --reload

# Using Python directly
python -m src.main --yaml_file yaml_files/main.yml
```

## Configuration

1. **Copy `.env.example` to `.env`:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your API keys:**
   ```bash
   # VLM Service
   VLM_API_KEY=your-vlm-api-key
   VLM_BASE_URL=http://localhost:8001
   VLM_MODEL_NAME=chat_model

   # TTS Service
   TTS_API_KEY=your-tts-api-key
   TTS_BASE_URL=http://localhost:8080

   # LLM Service (for agent)
   LLM_API_KEY=your-llm-api-key
   LLM_BASE_URL=http://localhost:55120/v1
   LLM_MODEL=chat_model
   ```

3. **Service configurations are in YAML files:**
   - `yaml_files/main.yml` - Main service registry
   - `yaml_files/services/tts_service/fish_speech.yml` - TTS config
   - `yaml_files/services/vlm_service/openai_compatible.yml` - VLM config

## Key Changes

### Before (Old Way ❌)
```python
from src.services import _tts_service, _vlm_service

# Services initialized in __init__.py (confusing)
audio = _tts_service.tts_engine.generate_speech("Hello")
```

### After (New Way ✅)
```python
from src.services import get_tts_service, get_vlm_service

# Services initialized explicitly from YAML configs
tts_service = get_tts_service()
audio = tts_service.generate_speech("Hello")
```

## Benefits

1. ✅ **Clean imports** - No more `_tts_service.tts_engine` nesting
2. ✅ **Secure** - API keys in `.env`, not in YAML files
3. ✅ **Flexible** - Easy to switch providers via YAML config
4. ✅ **Readable** - Clear initialization with `initialize_services()`
5. ✅ **Testable** - Easy to mock or use different configs

## See Also

- Full documentation: [docs/service_initialization_guide.md](docs/service_initialization_guide.md)
- Main config: [yaml_files/main.yml](yaml_files/main.yml)
