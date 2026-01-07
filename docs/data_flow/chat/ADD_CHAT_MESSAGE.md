# ADD_CHAT_MESSAGE Data Flow

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
    participant API as Back-End (REST API)

    Note over User, FE: Trigger
    User->>FE: User sends a new chat message (Text/Image)

    Note over FE: Optimistic Update
    FE->>FE: Append user message to Chat History
    FE-->>User: Display user message immediately

    Note over FE, BE: Data Flow
    FE->>BE: Send Websocket message 'chat_message'
    Note right of FE: params: { session_id (null for new chat),<br/>agent_id, user_id, content, images... }
    
    activate BE
    
    alt New Chat (session_id is null)
        BE->>BE: Generate new UUID for session_id
    else Existing Chat
        BE->>BE: Use provided session_id
    end
    
    loop Streaming Response
        BE-->>FE: stream_start (session_id)
        
        par Parallel Processing
            rect rgb(240, 248, 255)
                note right of FE: Text Stream
                BE-->>FE: stream_token (chunk)
                FE->>FE: Append text chunk to AI message
                FE-->>User: Update AI response in real-time
            end
        and 
            rect rgb(255, 245, 238)
                note right of FE: Audio & VRM Motion Synthesis
                BE-->>FE: tts_ready_chunk (text, emotion, )
                
                par Async Preparation
                    FE->>API: POST /v1/tts/synthesize
                    API-->>FE: Return Audio Data (Base64)
                and Motion Selection Logic
                    FE->>FE: Check Emotion
                end
                
                FE->>FE: Queue Task (Audio + Motion + Expression)
                FE-->>User: Play audio with Lip Sync
                FE-->>User: Play VRM Motion & Expression
            end
        and 
            rect rgb(240, 255, 240)
                note right of FE: Tool Execution
                BE-->>FE: tool_call (name, args)
                FE->>FE: Display tool call in UI
            end
        end

        BE->>API: Save conversation turn to REST API
        API-->>BE: Success
        BE-->>FE: stream_end (session_id)
        deactivate BE
        
        alt New Chat Session Capture
            Note over FE: If currentSessionId was null
            FE->>FE: Capture session_id from stream_end
            FE->>FE: Update currentSessionId
            FE->>FE: Preserve optimistic UI state (no reload)
            FE->>API: Refresh session list
            API-->>FE: Updated sessions
            FE-->>User: Show new session in sidebar
        else Existing Session
            Note over FE: Session already tracked
            FE->>FE: Continue with current session
        end
    end
```

## Detailed Point about Audio Synthesis

1. **Trigger**: Backend analyzes the stream and determines a complete sentence/phrase is ready for speech.
2. **Notification**: Backend sends `tts_ready_chunk` WebSocket message containing **text** and optional **emotion**.
3. **Synthesis**: Frontend receives the message and immediately calls `POST /v1/tts/synthesize` to convert the text chunk to audio.
4. **Queueing**: The resulting audio is added to a sequential task queue. Note. 오디오 데이터만 넣는 것이 아니라, 결정된 모션 키값도 함께 큐에 넣습니다.
    - Queue Item: { audio_data, motion_name, blendshape_name }
5. **Playback**: Audio is played in order, synchronized with Live2D lip-sync movements.
    - Audio: 재생 시작 + 립싱크 모듈 연동.
    - VRM: AnimationPlayer로 motion_name 재생 + blendshape_name 적용.

## Key Implementation Details

### Session ID Capture Logic

- **New Chat**: When `session_id` is `null`, backend generates a UUID and returns it in the `stream_end` event.
- **Frontend Capture**: Frontend checks if `currentSessionId` is null in the `stream_end` handler. If so, it captures and stores the backend-generated UUID.
- **Optimistic UI Preservation**: The context prevents reloading messages when transitioning from `null` → UUID to avoid UI flicker.
- **Subsequent Messages**: Next message uses the captured `session_id`, ensuring all messages belong to the same session.

### STM Persistence

- Backend automatically saves both user and assistant messages to STM (Short Term Memory) when processing completes.
- Frontend does not directly call STM APIs for saving; it only reads history when loading sessions.
- Session persistence is guaranteed by the backend's `stream_end` logic.

## Appendix

- [Backend WebSocket API](../../websocket/WEBSOCKET_API_GUIDE.md)
- [TTS Synthesize API](../../api/TTS_Synthesize.md)
