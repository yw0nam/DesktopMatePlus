# Release Notes - VLM Service Removal, OpenAI-Compatible Image Format

Updated: 2026-03-11

## [refactor/agent_image_support] (2026-03-11)

> VLM service fully removed. Agent service now receives images in OpenAI-compatible format via WebSocket.

### Breaking Changes

* **VLM service removed** — `src/services/vlm_service/` and all related code deleted. Clients using `/vlm/analyze` must migrate to Agent Service via WebSocket with `support_image: true`.
* **`images` field format changed** — `ChatMessage.images` is now `List[ImageContent]` (OpenAI-compatible objects), not `List[str]`.

  **Before (old format, no longer accepted):**
  ```json
  { "images": ["data:image/png;base64,...", "https://example.com/img.png"] }
  ```

  **After (new format, required):**
  ```json
  {
    "images": [
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,...", "detail": "auto"}},
      {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}}
    ]
  }
  ```

### Removed

* `src/services/vlm_service/` — VLM service implementation
* `src/configs/vlm/` — VLM configuration models
* `src/api/routes/vlm.py` — `/vlm/analyze` endpoint
* `src/models/vlm.py` — `VLMRequest`, `VLMResponse` models
* `yaml_files/services/vlm_service/` — VLM YAML config
* `tests/api/test_vlm_api_integration.py`
* `tests/services/test_vlm_service.py`
* `tests/services/test_vlm_utils.py`
* `HealthService.check_vlm()` — VLM no longer included in health checks (4 modules: TTS, Agent, LTM, STM)

### New

* `ImageUrl`, `ImageContent` Pydantic models in `src/models/websocket.py` — enforce OpenAI-compatible image structure at ingestion.

### Changed

* `ChatMessage.images`: `Optional[List[str]]` → `Optional[List[ImageContent]]`
* `handlers.py` image processing: removed `prepare_image_for_vlm()` call; images passed directly as `img.model_dump()` to message content.
* `initialize_services()` return type: `(TTS, Agent, STM, LTM)` — VLM removed from tuple.
* Health endpoint now reports 4 modules instead of 5.

### Related Documents

* [WebSocket ChatMessage](../websocket/WebSocket_ChatMessage.md)
* [Agent Service](../feature/service/Agent_Service.md)
* [Service Layer](../feature/service/README.md)
* [REST API Guide](../api/REST_API_GUIDE.md)
