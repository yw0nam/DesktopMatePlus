# SWITCH_SESSION 데이터 플로우

## DATA FLOW DIAGRAM

```mermaid
sequenceDiagram
    actor User as User
    participant FE as Godot (Manager)
    participant BE_API as FastAPI (REST)
    participant BE_WS as WebSocket (Stream)

    Note over User, FE: 1. 세션 변경 (View Update)
    User->>FE: 세션 B 클릭
    FE->>FE: current_session_id = "Session_B" (즉시 변경)
    FE->>BE_API: GET /history?session_id=Session_B
    BE_API-->>FE: History JSON (과거 대화 로그)
    FE->>FE: 채팅창 UI 초기화 및 렌더링

    Note over User, FE: 2. 메시지 전송 (Action)
    User->>FE: "안녕" 입력
    FE->>BE_WS: send_json({<br/> "type": "chat_message",<br/> "session_id": "Session_B",<br/> "content": "안녕"<br/>})

    activate BE_WS
    Note right of BE_WS: [Backend Logic]<br>1. packet.session_id 확인<br>2. STM에서 History Load<br>3. LLM Invoke (History + "안녕")

    loop Response Stream
        BE_WS-->>FE: stream_token ("반가")
        BE_WS-->>FE: stream_token ("워요")
        BE_WS-->>FE: tts_ready_chunk ("반가워요")
    end
    BE_WS-->>FE: stream_end
    deactivate BE_WS
```

## Cautions

현재 방식에서 유일한 약점은 **"FE 변수 업데이트 타이밍"**

시나리오:

1. 사용자가 세션 A를 보고 있음.
2. 세션 B를 클릭함. (current_session_id가 B로 바뀜)
3. 하지만 네트워크가 느려서 세션 B의 History(REST)가 로딩되는 데 2초 걸림.
4. 화면엔 여전히 세션 A의 대화 내용이 남아있거나, 로딩 중임.
5. 사용자가 급해서 채팅창에 "야" 라고 치고 엔터.

이때, current_session_id는 이미 B로 바뀌었으므로, 사용자는 A의 화면을 보면서 B의 방에 "야"라고 말하게 됨

-> 해결책 (FE 구현 시 반영): 세션을 전환하는 순간(SWITCH_SESSION), REST 응답이 와서 UI가 렌더링될 때까지 채팅 입력창(Input Box)을 disabled 처리하거나, 로딩 스피너(Overlay)로 막아두기.

## Appendix

- [GetChatHistory API](../../../../backend//docs/api/STM_GetChatHistory.md)
- [ListChatHistory API](../../../../backend//docs/api/STM_ListChatHistory.md)
- [Session List 데이터 플로우](./LIST_SESSION.md)
- [API Service](../../feature/service/api-service.md)
