# Proactive Talking — Feasibility Study

**작성일:** 2026-04-14
**상태:** 구현 가능 (인프라 준비 완료)

## 개요

유저 입력 없이 서버가 먼저 말을 거는 기능.
예) 일정 시간 idle 후 자동 발화, Slack 이벤트 후 캐릭터 발화, 특정 시각 인사 등.

---

## 판정: ✅ 구현 가능 (기존 인프라 재활용)

### 근거

| 항목 | 판정 | 근거 파일 |
|------|------|-----------|
| WS 서버→클라이언트 push | ✅ 가능 | `websocket_manager.py:227-242` — `send_message()` / `broadcast_message()` 존재 |
| Agent 유저입력 없이 실행 | ✅ 가능 | `openai_chat_agent.py:196` — `stream(messages=[], ...)` 빈 입력 허용 |
| 백그라운드 태스크 인프라 | ✅ 존재 | `task_sweep_service/sweep.py:37-65` — `BackgroundSweepService` 패턴 증명됨 |
| TTS → WS push 서버 주도 | ✅ 가능 | `event_handlers.py:118` — 이벤트 파이프라인이 유저 입력에 종속 안 됨 |
| Slack → proactive 트리거 | ✅ 가능 | `slack.py:61` — `asyncio.create_task` 기반 비동기 처리 |
| APScheduler (특정 시각) | ⚠️ 미설치 | `uv add apscheduler` 필요 |

---

## 구현 방향

### Phase 1 — Idle Timer 트리거 (최소 구현)

`ConnectionState` 또는 `MessageProcessor`에 마지막 유저 메시지 타임스탬프를 기록하고,
백그라운드 태스크(`asyncio.create_task`)가 주기적으로 idle 시간을 확인한다.

```
ConnectionState.last_user_message_at: datetime
  ↓ (idle > threshold)
ProactiveService._trigger_proactive(connection_id)
  ↓
agent_service.stream(messages=[], session_id=..., trigger_type="proactive")
  ↓ (기존 파이프라인 재사용)
EventHandler → TTS → websocket_manager.send_message()
```

**신규 파일**: `src/services/proactive_service/` (≈200줄)
**수정 파일**: `websocket_manager.py` (disconnect 시 idle task cancel), `main.py` (서비스 등록)
**스키마 변경**: `AgentState`에 `trigger_type: str` 추가

### Phase 2 — APScheduler 기반 시각 트리거

특정 시각(예: 아침 9시 인사)에 모든 활성 세션에 proactive 메시지 발송.

```
AsyncIOScheduler (cron: 09:00)
  ↓
session_registry.get_active_connections()
  ↓
각 connection별 _trigger_proactive() 병렬 실행
```

**의존성 추가**: `apscheduler>=3.10`
**서비스 등록**: `service_manager.py` init order 맨 끝 (다른 서비스 의존)

### Phase 3 — 외부 이벤트 웹훅 트리거

`POST /v1/proactive/trigger` 엔드포인트로 외부 시스템(Slack, 알림 서버 등)이 발화를 요청.

```json
{
  "session_id": "...",
  "persona_id": "...",
  "trigger_reason": "slack_mention"
}
```

---

## 아키텍처 고려사항

- **Session lock**: proactive 실행 중 유저 메시지 동시 처리 방지 — 기존 "concurrent turn protection (4002)" 로직 활용
- **LTM context**: 빈 입력으로 실행 시 LTM middleware가 컨텍스트를 주입해야 의미 있는 발화 생성 가능
- **Zombie task 방지**: WebSocket disconnect 시 idle watcher `task.cancel()` 필수
- **무한 루프 방지**: proactive 발화 후 idle timer 리셋 필수

---

## 예상 작업량

| Phase | 신규 코드 | 수정 파일 수 | 난이도 |
|-------|-----------|-------------|--------|
| Phase 1 (idle timer) | ~200줄 | 3개 | 낮음 |
| Phase 2 (APScheduler) | ~150줄 | 2개 + 의존성 1개 | 중간 |
| Phase 3 (웹훅) | ~100줄 | 1개 | 낮음 |

---

## 블로커

없음. 모든 인프라(WS push, agent 실행, 백그라운드 태스크) 준비 완료.
