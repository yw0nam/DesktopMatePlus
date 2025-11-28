# VLM Service

## 1. Synopsis

- **Purpose**: Vision-Language Model for image analysis and understanding
- **I/O**: Image(s) + Prompt → Text response

## 2. Core Logic

### Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `initialize_model()` | - | `BaseChatModel` |
| `is_healthy()` | - | `(bool, str)` |
| `generate_response()` | image, prompt | `str` |

### Supported Image Formats

| Format | Type | Example |
|--------|------|---------|
| URL | `str` | `"https://example.com/image.png"` |
| Bytes | `bytes` | Raw image data |
| Base64 | `str` | `"data:image/png;base64,..."` |
| List | `list` | Multiple images |

### Implementation: OpenAICompatibleVLM

- OpenAI-compatible VLM API (vLLM)
- LangChain integration
- Customizable system prompts

### Configuration

```yaml
# yaml_files/services/vlm_service/openai_compatible.yml
vlm_config:
  type: "openai_compatible"
  configs:
    temperature: 0.7
    top_p: 0.9
    model_name: "chat_model"
    openai_api_base: "http://localhost:5530/v1"
```

## 3. Usage

```python
from src.services import get_vlm_service

vlm = get_vlm_service()

# Analyze image from bytes
with open("image.png", "rb") as f:
    image_bytes = f.read()

response = vlm.generate_response(
    image=image_bytes,
    prompt="What is shown in this image?"
)
print(response)

# Analyze image from URL
response = vlm.generate_response(
    image="https://example.com/image.png",
    prompt="Describe this image in detail."
)

# Analyze multiple images
response = vlm.generate_response(
    image=[image_bytes_1, image_bytes_2],
    prompt="Compare these two images."
)
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [VLM Configuration](../config/VLM_Config_Fields.md)
- [VLM API Endpoint](../../api/VLM_Analyze.md)
