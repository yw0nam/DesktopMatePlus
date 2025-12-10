# WebSocket and Message Processor Logic Evaluation

**Date:** December 10, 2025
**Module:** `src/services/websocket_service/message_processor`

## 1. Executive Summary

The message processor architecture is well-structured, employing a clear separation of concerns and robust asynchronous patterns. The use of separate producer (agent stream) and consumer (TTS processing) queues allows for efficient, non-blocking operation. However, a critical memory leak exists where completed conversation turns are never removed from memory during the lifecycle of a connection. Additionally, there is a minor risk of data loss in the text processing pipeline.

## 2. Architecture Assessment

### Strengths
- **Modular Design:** The separation into `MessageProcessor`, `EventHandler`, and `TaskManager` promotes maintainability and testability.
- **Concurrency Model:** The use of `asyncio.Queue` to decouple the `AgentService` stream from the TTS processing pipeline is excellent. It ensures that slow TTS processing does not block the generation of new tokens.
- **Resource Management:** The system handles interruptions gracefully, ensuring tasks are cancelled and queues are drained.
- **Logging:** Comprehensive structured logging (via `loguru`) provides good visibility into system state and tool execution.

### Weaknesses & Risks
1.  **Memory Leak (High Severity):**
    - The `MessageProcessor.turns` dictionary accumulates `ConversationTurn` objects indefinitely.
    - While `cleanup()` releases resources like tasks and queues, the turn object itself remains in memory.
    - `cleanup_completed_turns()` exists but is **never called automatically** during normal operation (only on shutdown with delay).
    - **Impact:** Long-lived WebSocket connections (e.g., dashboards, continuous sessions) will experience unbounded memory growth.

2.  **Potential Data Loss (Medium Severity):**
    - The wrapper `TextChunkProcessor.flush` in `src/services/websocket_service/text_processors.py` assumes that the underlying `_delegate.finalize()` returns at most one string.
    - Logic: `if len(sentences) > 1: logger.debug(...); return sentences[0]`
    - **Impact:** If the underlying `AgentTextChunkProcessor` (in `agent_service`) is updated to return multiple buffered sentences, this wrapper will silently drop all but the first one.

3.  **Timeout Configuration (Low Severity):**
    - `INTERRUPT_WAIT_TIMEOUT` is set to `1.0` second.
    - **Impact:** In high-load scenarios or with complex regex processing, draining the token queue might take longer than 1 second, potentially causing premature cancellation of the final TTS chunks during an interrupt.

## 3. Recommendations

### Immediate Fixes
1.  **Fix Memory Leak:**
    - Modify `MessageProcessor.start_turn` to call `self.cleanup_completed_turns(max_age_seconds=3600)` (or a shorter interval). This ensures that starting a new turn automatically garbage-collects old ones.

2.  **Harden Text Processing:**
    - Update `TextChunkProcessor.flush` in `src/services/websocket_service/text_processors.py` to handle and join multiple sentences if returned, or process them sequentially.

### Improvements
1.  **Configurable Timeouts:**
    - Move `INTERRUPT_WAIT_TIMEOUT` to the `MessageProcessor` configuration or `settings.py` to allow adjustment for different deployment environments.

2.  **Periodic Cleanup Task:**
    - Alternatively to the "cleanup on start" approach, `MessageProcessor` could spawn a background task that runs `cleanup_completed_turns` periodically, though this adds complexity to the lifecycle management. The "cleanup on start" approach is simpler and sufficient for most request-response patterns.
