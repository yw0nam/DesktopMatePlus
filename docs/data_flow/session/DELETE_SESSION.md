# DELETE_SESSION 데이터 플로우

## DATA FLOW DIAGRAM

```mermaid
sequenceDiagram
    actor User as User (Client)
    participant FE as Front-End (Sidebar)
    participant BE as Back-End (STM API)

    Note over User, FE: Trigger
    User->>FE: 세션 우측 휴지통 아이콘 클릭

    Note over FE, BE: 1. Delete Request
    FE->>BE: DELETE /v1/stm/sessions/{session_id}
    Note right of FE: params: { agent_id, user_id }
    activate BE
    BE->>BE: DB에서 세션 삭제 처리
    BE-->>FE: 200 OK (삭제 성공 여부)
    deactivate BE

    Note over FE, BE: 2. List Refresh (Data Sync)
    alt 삭제 성공 시
        FE->>BE: GET /stm/sessions (user_id, agent_id)
        activate BE
        BE-->>FE: 갱신된 Session List 반환
        deactivate BE

        Note over FE, User: UI Update
        FE->>FE: Sidebar 목록 상태(State) 업데이트
        FE-->>FE: (If active session deleted) Reset to New Chat
        FE-->>User: 세션이 삭제된 최신 목록 표시
    else 삭제 실패 시
        FE-->>User: 삭제 실패 알림 (Toast/Alert)
    end
```

## Appendix

- [DeleteSession API](../../../../backend//docs/api/STM_DeleteSession.md)
- [ListChatHistory API](../../../../backend//docs/api/STM_ListChatHistory.md)
- [Session List 데이터 플로우](./LIST_SESSION.md)
- [API Service](../../feature/service/api-service.md)
