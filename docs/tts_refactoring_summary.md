# TTS Service Refactoring Summary

## Date: October 19, 2025

## Overview
Updated the TTS (Text-to-Speech) service architecture to use a cleaner, more maintainable factory pattern with unified interface and configuration.

## Key Changes

### 1. Architecture Simplification

**Before:**
- Complex multi-layer architecture: `TTSClient` → `TTSService` → `FishSpeechProvider` → `FishSpeechTTS`
- Global singleton pattern with `initialize_tts_client()` and `get_tts_client()`
- Service wrapper pattern with primary/fallback provider support

**After:**
- Simple direct architecture: `TTSFactory` → `FishSpeechTTS` (extends `TTSService`)
- Factory pattern for creating TTS engines
- Global service storage using module-level container
- Cleaner separation of concerns

### 2. Files Modified

#### Core Service Files
- **`src/services/tts_service/service.py`**: Simplified to abstract base class only
- **`src/services/tts_service/fish_speech.py`**: Now inherits from `TTSService` directly
- **`src/services/tts_service/__init__.py`**: Updated exports for new pattern
- **`src/services/__init__.py`**: Added global TTS service container

#### New Files
- **`src/services/tts_service/tts_factory.py`**: Factory for creating TTS engines
- **`src/configs/tts.py`**: Configuration models for TTS settings

#### Deleted Files
- **`src/services/tts_service/tts_client.py`**: Removed redundant client wrapper

#### Integration Files
- **`src/main.py`**: Updated to use factory pattern for initialization
- **`src/services/health.py`**: Updated to check TTS engine directly

#### Test Files
- **`tests/test_tts_synthesis.py`**: Completely rewritten for new architecture
- **`tests/test_health_endpoint.py`**: Updated TTS health check test

#### Example Files
- **`examples/tts_synthesis_demo.py`**: Updated to demonstrate new factory pattern

### 3. API Changes

#### Old API
```python
from src.services.tts_service import initialize_tts_client, synthesize_speech

# Initialize
client = initialize_tts_client(fish_speech_url="http://localhost:8080/v1/tts")

# Use
audio_bytes = synthesize_speech("Hello world")
```

#### New API
```python
from src.services.tts_service import TTSFactory

# Create engine
tts_engine = TTSFactory.get_tts_engine(
    "fish_local_tts",
    base_url="http://localhost:8080/v1/tts",
    api_key="optional_key"
)

# Use
audio_bytes = tts_engine.generate_speech("Hello world", output_format="bytes")
```

### 4. Method Signature Changes

#### FishSpeechTTS.generate_speech()
**Before:** `generate_speech(raw_text: str, ...)`
**After:** `generate_speech(text: str, ...)`

#### Health Check
**Before:** Returns `dict[str, dict[str, object]]` with primary/fallback structure
**After:** Returns `tuple[bool, str]` with (is_healthy, message)

### 5. Configuration Support

Added `TTSConfig` and `FishLocalTTSConfig` Pydantic models in `src/configs/tts.py` to support:
- Multiple TTS providers (extensible)
- Comprehensive Fish Speech configuration options
- Type-safe configuration validation

### 6. Test Coverage

**Updated Tests:**
- `TestTTSFactory`: Tests factory pattern and engine creation
- `TestFishSpeechTTS`: Tests direct TTS engine functionality
- `TestTTSConfiguration`: Tests configuration with custom parameters
- `TestTTSIntegration`: Integration tests with mocked API

**Test Results:**
- All 11 TTS-specific tests pass ✅
- All 50 overall tests pass ✅
- 7 tests skipped (display-dependent screen capture tests)

### 7. Benefits of Refactoring

1. **Simpler Architecture**: Reduced layers and complexity
2. **Better Testability**: Direct testing of TTS engines without wrapper layers
3. **Easier Extension**: Factory pattern makes adding new providers straightforward
4. **Type Safety**: Better type hints and configuration validation
5. **Cleaner Code**: Removed redundant abstractions
6. **Maintained Compatibility**: Health checks and main integration still work

### 8. Migration Guide

For code using the old API:

```python
# OLD
from src.services.tts_service import initialize_tts_client, get_tts_client
client = initialize_tts_client(fish_speech_url="http://localhost:8080/v1/tts")
audio = client.synthesize_speech("Hello")

# NEW
from src.services.tts_service import TTSFactory
tts_engine = TTSFactory.get_tts_engine(
    "fish_local_tts",
    base_url="http://localhost:8080/v1/tts"
)
audio = tts_engine.generate_speech("Hello", output_format="bytes")
```

### 9. Running Tests

```bash
# Run TTS-specific tests
uv run pytest tests/test_tts_synthesis.py -v

# Run all tests
uv run pytest tests/ -v

# Run demo
uv run python examples/tts_synthesis_demo.py
```

### 10. Future Enhancements

The new architecture makes it easy to:
1. Add new TTS providers (OpenAI TTS, Azure TTS, etc.)
2. Implement provider-specific configurations
3. Add provider selection logic in the factory
4. Support multiple concurrent TTS engines

## Conclusion

The refactoring successfully simplified the TTS service architecture while maintaining all functionality and improving testability. All tests pass, and the application starts correctly with the new structure.
