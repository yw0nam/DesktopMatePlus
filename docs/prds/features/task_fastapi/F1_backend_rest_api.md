# F1: Backend REST APIs

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Expose TTS, VLM, and Memory as REST for MCP tools.
- **I/O**: HTTP JSON -> service output (base64 audio, VLM text, memory records).

## 2. Core Logic
- **Step 1**: Define Pydantic request/response models for `/v1/tts`, `/v1/vlm`, `/v1/memory`.
- **Step 2**: Implement routers that wrap existing services:
  - `POST /v1/tts/synthesize`
  - `POST /v1/vlm/analyze`
  - `POST /v1/memory/stm/add`, `GET /v1/memory/stm/history`
  - `POST /v1/memory/ltm/add`, `GET /v1/memory/ltm/search`
- **Step 3**: Add `X-API-Key` middleware for `/v1/*` only.
- **Step 4**: Add validation limits (image size, max text length, base64 decoding errors).
- **Step 5**: Add OpenAPI schema and integration tests with service mocks.
- **Constraints**:
  - Reject missing/invalid API key with 401.
  - Return 413 for oversized payloads.
  - Local response time target: <= 50ms with mocks.

## 3. Usage
- Happy path: `POST /v1/tts/synthesize` with a short text returns base64 audio + duration.

---

## Appendix (Reference & Extensions)
### A. Troubleshooting
- If VLM image validation fails, confirm base64 encoding and size limit.

### B. Related Documents
- [F2_sse_client.md](F2_sse_client.md)
- [NANOCLAW_INTEGRATION_PRD.md](../NANOCLAW_INTEGRATION_PRD.md)

### C. Test Scenarios
- `POST /v1/tts/synthesize` returns base64 + duration for short text.
- Missing `X-API-Key` returns 401 on `/v1/*`.
- Oversized image payload returns 413 on `/v1/vlm/analyze`.
- STM CRUD cycle stores and returns messages for a session.
