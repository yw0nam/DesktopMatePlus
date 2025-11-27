# REST API Guide

This document provides a detailed guide to the RESTful API endpoints available in the DesktopMatePlus backend.

## Base URL

All API endpoints are prefixed with `/v1`.

- **Development Server**: `http://127.0.0.1:5500/v1`

## Endpoints

The REST API is organized by service.

### Short-Term Memory (STM)

The STM service is responsible for managing chat history.

- **[List Sessions](./STM_ListSessions.md)**: `GET /stm/sessions`
- **[Get Chat History](./STM_GetChatHistory.md)**: `GET /stm/chat-history`
- **[Add Chat History](./STM_AddChatHistory.md)**: `POST /stm/chat-history`
- **[Update Session Metadata](./STM_UpdateSessionMetadata.md)**: `PATCH /stm/sessions/{session_id}/metadata`
- **[Delete Session](./STM_DeleteSession.md)**: `DELETE /stm/sessions/{session_id}`

### Text-to-Speech (TTS)

The TTS service converts text into audible speech.

- **[Synthesize Speech](./TTS_Synthesize.md)**: `POST /tts/synthesize`

### Vision and Language Model (VLM)

The VLM service analyzes images and provides descriptions or answers questions about them.

- **[Analyze Image](./VLM_Analyze.md)**: `POST /vlm/analyze`
