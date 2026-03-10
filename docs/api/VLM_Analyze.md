# VLM: Analyze Image

Updated: 2026-03-10

> **⚠️ DEPRECATED (2026-03-10)**: This endpoint is deprecated. AgentService now natively supports image+text input. Use the WebSocket chat interface with image content instead.

## 1. Synopsis

- **Purpose**: Analyze images using Vision-Language Model (captioning, VQA)
- **I/O**: `POST { image, prompt? }` → `{ description }`
- **Status**: **Deprecated**

## 2. Core Logic

### Endpoint

`POST /v1/vlm/analyze`

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | string | Yes | Base64-encoded image or URL |
| `prompt` | string | No | Analysis prompt (default: "Describe this image") |

### Response

**Success (200)**:
```json
{ "description": "A golden retriever playing in a sunny park." }
```

**Errors**: `422` (missing image), `401` (unauthorized), `500` (processing failed)

## 3. Usage

```bash
curl -X POST "http://127.0.0.1:5500/v1/vlm/analyze" \
  -H "Content-Type: application/json" \
  -d '{ "image": "https://example.com/image.jpg", "prompt": "What color is the dog?" }'
```

---

## Appendix

### A. Use Cases

- Image captioning
- Visual question answering
- Object detection descriptions

### B. Related Documents

- [REST API Guide](./REST_API_GUIDE.md)
