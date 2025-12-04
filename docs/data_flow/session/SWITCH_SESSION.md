# SWITCH_SESSION 데이터 플로우

## DATA FLOW DIAGRAM

```mermaid
sequenceDiagram
    actor User as User (Client)
    participant FE as Front-End (Sidebar/Chat)
    participant BE as Back-End (STM API)

    Note over User, FE: Precondition (전제 조건)
    User->>FE: 사이드바의 Session 탭 클릭 (Session List 로딩됨)

    Note over User, FE: Trigger
    User->>FE: 특정 세션(Session Item) 클릭

    Note over FE, BE: Data Flow
    FE->>BE: GET /v1/stm/chat-history
    Note right of FE: params: { session_id, agent_id, user_id }
    activate BE
    BE-->>FE: Chat History 데이터 반환 (JSON)
    deactivate BE

    Note over FE, User: UI Update
    FE->>FE: 기존 대화 화면 초기화 & 데이터 파싱
    FE-->>User: 메인 화면에 대화 기록(Chat History) 렌더링
```

## Appendix

- [GetChatHistory API](../../../../backend//docs/api/STM_GetChatHistory.md)
- [ListChatHistory API](../../../../backend//docs/api/STM_ListChatHistory.md)
- [Session List 데이터 플로우](./LIST_SESSION.md)
- [API Service](../../feature/service/api-service.md)
