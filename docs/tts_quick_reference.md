# TTS Service Quick Reference Guide

## Initialization

### In Application (main.py)
```python
from src.services.tts_service.tts_factory import TTSFactory
from src.services import _tts_service

# Create TTS engine
tts_engine = TTSFactory.get_tts_engine(
    "fish_local_tts",
    base_url="http://localhost:8080/v1/tts",
    api_key=None  # Optional
)

# Store globally
_tts_service.tts_engine = tts_engine
```

### In Scripts/Tests
```python
from src.services.tts_service import TTSFactory

# Create TTS engine
tts_engine = TTSFactory.get_tts_engine(
    "fish_local_tts",
    base_url="http://localhost:8080/v1/tts"
)
```

## Usage

### Basic Speech Generation
```python
# Generate audio as bytes
audio_bytes = tts_engine.generate_speech(
    text="Hello, world!",
    output_format="bytes"
)
```

### Base64 Output
```python
# Generate audio as base64 string
audio_base64 = tts_engine.generate_speech(
    text="Hello, world!",
    output_format="base64"
)
```

### Save to File
```python
# Generate and save to file
success = tts_engine.generate_speech(
    text="Hello, world!",
    output_format="file",
    output_filename="output.wav"
)
```

### With Voice Reference
```python
# Use specific voice reference
audio_bytes = tts_engine.generate_speech(
    text="Hello, world!",
    reference_id="ナツメ",
    output_format="bytes"
)
```

## Health Check

```python
# Check if TTS is healthy
is_healthy, message = tts_engine.is_healthy()
if is_healthy:
    print(f"TTS is healthy: {message}")
else:
    print(f"TTS is unhealthy: {message}")
```

## Configuration Options

### Full Configuration
```python
tts_engine = TTSFactory.get_tts_engine(
    "fish_local_tts",
    base_url="http://localhost:8080/v1/tts",
    api_key="your_api_key",
    seed=42,  # For reproducible generation
    streaming=False,
    use_memory_cache="off",
    chunk_length=200,
    max_new_tokens=1024,
    top_p=0.7,
    repetition_penalty=1.2,
    temperature=0.7
)
```

### Using Config File
```python
from src.configs.tts import TTSConfig, FishLocalTTSConfig

# Create config
config = TTSConfig(
    tts_model="fish_local_tts",
    fish_local_tts=FishLocalTTSConfig(
        base_url="http://localhost:8080/v1/tts",
        api_key=None,
        temperature=0.8
    )
)

# Create engine from config
tts_engine = TTSFactory.get_tts_engine(
    config.tts_model,
    **config.fish_local_tts.model_dump()
)
```

## Testing

### Unit Test Example
```python
from unittest.mock import Mock, patch
from src.services.tts_service import TTSFactory, FishSpeechTTS

@patch("src.services.tts_service.fish_speech.requests.post")
def test_tts_generation(mock_post):
    # Mock API response
    mock_response = Mock()
    mock_response.content = b"fake_audio_data"
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Create TTS engine
    tts = FishSpeechTTS(url="http://localhost:8080/v1/tts")

    # Test
    result = tts.generate_speech("Hello", output_format="bytes")
    assert result == b"fake_audio_data"
```

## Error Handling

```python
try:
    audio_bytes = tts_engine.generate_speech(
        text="Hello, world!",
        output_format="bytes"
    )

    if audio_bytes is None:
        print("TTS generation returned None")
    else:
        print(f"Generated {len(audio_bytes)} bytes")

except Exception as e:
    print(f"TTS error: {e}")
```

## Adding New TTS Provider

1. Create new provider class inheriting from `TTSService`:
```python
# src/services/tts_service/my_tts.py
from src.services.tts_service.service import TTSService

class MyTTS(TTSService):
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key

    def generate_speech(self, text: str, **kwargs):
        # Implement speech generation
        pass

    def is_healthy(self) -> tuple[bool, str]:
        # Implement health check
        pass
```

2. Add to factory:
```python
# src/services/tts_service/tts_factory.py
def get_tts_engine(engine_type, **kwargs):
    if engine_type == "my_tts":
        from .my_tts import MyTTS
        return MyTTS(
            url=kwargs.get("url"),
            api_key=kwargs.get("api_key")
        )
    # ... other engines
```

3. Add configuration:
```python
# src/configs/tts.py
class MyTTSConfig(BaseModel):
    url: str
    api_key: str

class TTSConfig(BaseModel):
    tts_model: Literal["fish_local_tts", "my_tts"]
    my_tts: Optional[MyTTSConfig] = None
```

## Running Examples

```bash
# Run TTS demo
cd /home/spow12/codes/2025_lower/DesktopMatePlus
uv run python examples/tts_synthesis_demo.py

# Run TTS tests
uv run pytest tests/test_tts_synthesis.py -v

# Run all tests
uv run pytest tests/ -v
```

## Troubleshooting

### TTS Service Not Available
```
Error: Connection refused to http://localhost:8080
```
**Solution:** Start Fish Speech TTS server first

### Import Error
```
ImportError: cannot import name 'initialize_tts_client'
```
**Solution:** Update imports to use `TTSFactory` pattern

### Health Check Fails
```python
is_healthy, message = tts_engine.is_healthy()
# Returns: (False, "Fish Speech TTS returned empty result")
```
**Solution:** Check Fish Speech server is running and responding correctly
