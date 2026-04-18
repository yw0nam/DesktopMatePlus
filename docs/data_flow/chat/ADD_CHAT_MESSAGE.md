# ADD_CHAT_MESSAGE Data Flow

Updated: 2026-03-15

## Session Persistence Flow

### Correct Flow

1. **User clicks a session in the settings** → Load that session's history from STM and draw the chat_history to UI.

2. **User sends a message** → Should be stored to the currently selected session_id
   - Saving logic handled by backend. FE only handles `session_id` for that.
   - When `session_id` is null → backend perceives that as new chat.
   - When `session_id` is not null → backend perceives that as existing chat.

3. **When creating a new chat**, `session_id` starts as null, backend generates UUID, and frontend captures it from `stream_end` event.

## DATA FLOW DIAGRAM

```mermaid
sequenceDiagram
    actor User as User (Client)
    participant FE as Mate-Engine (Front-End)
    participant BE as Back-End (WebSocket Server)
    participant STM as Back-End (STM Service)

    Note over User, FE: Trigger
    User->>FE: User sends a new chat message (Text/Image)

    Note over FE: Optimistic Update
    FE->>FE: Append user message to Chat History
    FE-->>User: Display user message immediately

    Note over FE, BE: Data Flow
    FE->>BE: Send Websocket message 'chat_message'
    Note right of FE: params: { session_id (null for new chat),<br/>agent_id, user_id, content, images,<br/>tts_enabled (default: true), reference_id }

    activate BE

    alt New Chat (session_id is null)
        BE->>BE: Generate new UUID for session_id
    else Existing Chat
        BE->>BE: Use provided session_id
    end

    loop Streaming Response
        BE-->>FE: stream_start (session_id)

        Note right of BE: stream_token / tool_call / tool_result 이벤트는<br/>서버 내부 처리 전용 — FE로 전달되지 않음
        rect rgb(255, 245, 238)
            note right of FE: Audio & VRM Motion (Pre-synthesized by BE)
            BE-->>FE: tts_chunk (audio_base64, motion_name, blendshape_name, sequence)
            Note right of FE: audio_base64 is null if tts_enabled=false or synthesis failed
            FE->>FE: Queue Task (Audio + Motion + Expression)
            FE-->>User: Play audio with Lip Sync
            FE-->>User: Play VRM Motion & Expression
        end

        alt HitL Gate Trigger (위험 도구 호출 시)
            Note right of BE: MCP 도구 / delegate_task / mutating FS 도구 호출 시<br/>HumanInTheLoopMiddleware가 interrupt() 발생
            BE-->>FE: hitl_request (action_requests[], review_configs[])
            BE->>BE: TurnStatus → AWAITING_APPROVAL<br/>Producer exit (graph suspended at checkpoint)
            FE->>FE: 승인 UI 표시 (action_requests 별 approve/edit/reject)
            FE->>BE: hitl_response (decisions[])
            BE->>BE: TurnStatus → PROCESSING
            BE->>BE: agent_service.resume_after_approval(decisions)
            BE-->>FE: stream_start (재개)
            BE-->>FE: stream_token / tts_chunk (계속)
        end

        BE->>STM: save_turn(user+assistant messages)<br/>(asyncio.create_task — non-blocking)
        BE-->>FE: stream_end (session_id, content)
        Note right of FE: Guaranteed: all tts_chunk events arrive before stream_end
        deactivate BE

        alt New Chat Session Capture
            Note over FE: If currentSessionId was null
            FE->>FE: Capture session_id from stream_end
            FE->>FE: Update currentSessionId
            FE->>FE: Preserve optimistic UI state (no reload)
            FE->>BE: GET /v1/stm/sessions (user_id, agent_id)
            BE-->>FE: Updated sessions
            FE-->>User: Show new session in sidebar
        else Existing Session
            Note over FE: Session already tracked
            FE->>FE: Continue with current session
        end
    end
```

## Detailed Point about Audio Synthesis

1. **Trigger**: Backend analyzes the stream and determines a complete sentence/phrase is ready for speech.
2. **Synthesis**: Backend synthesizes audio via TTS engine (`asyncio.to_thread`) — parallel to text streaming.
3. **Delivery**: Backend sends `tts_chunk` WebSocket message containing pre-synthesized **audio_base64** (MP3), **emotion**, **motion_name**, **blendshape_name**, and **sequence**.
4. **Queueing**: Frontend receives the chunk and enqueues it directly — no additional API call needed.
   - Queue Item: `{ audio_base64, motion_name, blendshape_name, sequence }`
5. **Playback**: Audio is played in sequence order, synchronized with Live2D lip-sync movements.
   - Audio: MP3 base64 디코딩 후 재생 + 립싱크 모듈 연동.
   - VRM: AnimationPlayer로 `motion_name` 재생 + `blendshape_name` 적용.
   - `audio_base64 = null`인 경우 오디오 재생 생략, 모션은 그대로 적용.

## Key Implementation Details

### TTS Enabled / Disabled

- `tts_enabled: true` (default) — BE synthesizes audio; `audio_base64` is a base64 MP3 string.
- `tts_enabled: false` — BE skips synthesis; `audio_base64` is `null`. Avatar still plays motion/blendshape.
- `reference_id` — optional voice ID. `null` = engine default voice.

### TTS Barrier

- Backend awaits all `tts_chunk` tasks (max 10s) before sending `stream_end`.
- FE can safely assume that when `stream_end` arrives, all `tts_chunk` events for that turn have been delivered.

### Session ID Capture Logic

- **New Chat**: When `session_id` is `null`, backend generates a UUID and returns it in the `stream_end` event.
- **Frontend Capture**: Frontend checks if `currentSessionId` is null in the `stream_end` handler. If so, it captures and stores the backend-generated UUID.
- **Optimistic UI Preservation**: The context prevents reloading messages when transitioning from `null` → UUID to avoid UI flicker.
- **Subsequent Messages**: Next message uses the captured `session_id`, ensuring all messages belong to the same session.

### STM Persistence

- Backend automatically saves both user and assistant messages to STM (Short Term Memory) when processing completes.
- Frontend does not directly call STM APIs for saving; it only reads history when loading sessions.
- Session persistence is guaranteed by the backend's `stream_end` logic.

### HitL Gate

- **Trigger**: MCP 도구 / `delegate_task` / mutating FS 도구 호출 시 빌트인 `HumanInTheLoopMiddleware`가 interrupt 발생
- **Safe tools**: `search_memory`, `update_user_profile`, `read_file`, `list_directory`, `file_search` — HitL 없이 즉시 실행
- **Dangerous tools**: 모든 MCP 도구 + `delegate_task` + `_FS_MUTATING_TOOLS` (`write_file`, `copy_file`, `move_file`, `file_delete`, `edit_file`)
- **Resume**: FE에서 `hitl_response` (`decisions` 리스트) 전송 → `agent_service.resume_after_approval(decisions)` → graph 재개
- **Decisions**: 각 `action_request`에 1:1 대응하는 `{"type": "approve" | "edit" | "reject", ...}`. `edit`는 `edited_action.args`, `reject`는 선택적 `message`.
- 자세한 흐름: [`HITL_GATE_FLOW.md`](../agent/HITL_GATE_FLOW.md)

## Appendix

- [Backend WebSocket API](../../websocket/WEBSOCKET_API_GUIDE.md)
- [TTS Chunk Event](../../websocket/WebSocket_TtsChunk.md)
- [HitL Gate Flow](../../data_flow/agent/HITL_GATE_FLOW.md)
