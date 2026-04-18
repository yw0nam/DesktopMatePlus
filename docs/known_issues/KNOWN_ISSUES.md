# Known Issues

Updated: 2026-04-18

기술 부채 / 알려진 제약 / 후속 작업 추적. 항목은 severity 오름차순.

## HITL resume on FE disconnect

**Severity:** low
**Component:** websocket / agent
**발견:** 2026-04-18 (HITL 빌트인 migration)

FE 가 `hitl_request` 수신 후 응답 없이 연결이 끊기면 LangGraph 그래프가
Mongo checkpoint 에 suspended 상태로 잔존한다. 재연결 시 자동 resume 안 됨
— 사용자가 새 `chat_message` 를 보내면 구 checkpoint 는 버려진다.

TTL 기반 자동 cleanup 또는 reconnect 시 pending HITL 복원 UX 는 후속 이슈.
