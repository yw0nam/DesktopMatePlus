# REST API Guide

Updated: 2026-03-26

## 1. Synopsis

- **Purpose**: RESTful API for STM, LTM, TTS, and channel services
- **Interactive docs**: `http://127.0.0.1:5500/docs` (Swagger UI) — source of truth for schemas, parameters, and status codes

## 2. Non-Obvious Patterns

- **No auth on REST endpoints** — `/v1/stm/`, `/v1/ltm/`, `/v1/tts/`, `/v1/callback/` are internal-only (bound to `127.0.0.1`). Do not expose externally or add auth middleware.
- **503 = service not initialized** — All endpoints return `503` when their backing service hasn't completed lifespan init. Not a network error; wait for startup.
- **Slack `/events` is the exception** — Uses HMAC-SHA256 signature verification via `x-slack-signature` + `x-slack-request-timestamp` headers. See `src/services/channel_service/slack_service.py`.
- **STM routes are checkpointer-backed** — No separate STMService; history is persisted automatically by the LangGraph agent via `MongoDBSaver`.

---

## Appendix

### A. Related Documents

- [WebSocket API Guide](../websocket/CLAUDE.md)

### B. PatchNote

2026-03-26: Replaced endpoint catalog + individual files with Swagger (`/docs`) as source of truth. Retained only non-obvious architectural notes.
