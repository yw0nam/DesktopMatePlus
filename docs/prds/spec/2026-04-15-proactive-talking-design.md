# Proactive Talking Design Spec

**Date:** 2026-04-15
**Status:** Approved

## Overview

DesktopMate+ 백엔드에 proactive talking 기능을 추가한다. 유저의 입력 없이 AI 캐릭터가 먼저 말을 거는 기능으로, 3개 Phase를 한 번에 구현한다.

- **Phase 1**: Idle timer — 유저가 N초 동안 입력 없으면 1회 자동 발화
- **Phase 2**: APScheduler 기반 시간 트리거 — 특정 시각에 발화 (예: 아침 9시 인사)
- **Phase 3**: 외부 webhook 트리거 — `POST /v1/proactive/trigger`

## Architecture

단일 `ProactiveService`가 3가지 트리거를 모두 관리한다. `BackgroundSweepService` 패턴을 따른다.

```
src/services/proactive_service/
├── __init__.py
├── proactive_service.py    # ProactiveService (메인 서비스)
├── idle_watcher.py         # IdleWatcher (Phase 1)
├── schedule_manager.py     # ScheduleManager (Phase 2, APScheduler)
└── prompt_loader.py        # YAML 프롬프트 템플릿 로더

src/api/routes/proactive.py  # Phase 3 webhook endpoint

yaml_files/
├── proactive_prompts.yml    # 트리거별 프롬프트 템플릿
└── services.yml             # proactive 섹션 추가

personas.yml                 # idle_timeout_seconds 페르소나별 오버라이드
```

### Dependencies

- `WebSocketManager`: connection 조회 + 메시지 전송
- `AgentService`: LLM 호출
- `SessionLock`: 동시성 보호
- `SessionRegistry`: 활성 세션 조회 (Phase 2)
- `APScheduler`: 시간 기반 스케줄링 (신규 의존성, `uv add apscheduler`)

### Service Lifecycle

- `main.py` lifespan에서 `ProactiveService.start()` / `stop()` 등록
- `start()`: IdleWatcher 루프 + APScheduler 시작
- `stop()`: 둘 다 graceful shutdown (`task.cancel()` + `suppress(CancelledError)`)

## Phase 1: Idle Timer

### ConnectionState 변경

`ConnectionState`에 `last_user_message_at: float` 필드를 추가한다. `handlers.handle_chat_message()`에서 유저 메시지 수신 시 타임스탬프를 갱신한다.

### IdleWatcher 동작

1. 주기적 루프(`watcher_interval_seconds`, 기본 30초)로 모든 활성 connection을 순회
2. `now - last_user_message_at > idle_timeout` 이면 `trigger_proactive()` 호출
3. `idle_timeout`은 페르소나별 오버라이드 가능

### trigger_proactive() 공통 실행 흐름

모든 Phase가 이 함수를 공유한다:

1. `session_lock` 획득 시도 -> 실패 시 취소 (유저 턴 진행 중)
2. idle 재확인 — lock 획득 대기 중 유저가 메시지를 보냈으면 취소
3. 쿨다운 체크 — `last_proactive_at + cooldown > now` 이면 취소
4. 프롬프트 로딩 — `trigger_type` + 현재 시각 등으로 YAML 템플릿 렌더링
5. `agent_service.stream(messages=[SystemMessage(prompt)], session_id=...)`
6. 기존 `event_handlers` 파이프라인으로 TTS + WS push (`proactive: true` 태깅)
7. `last_proactive_at` 갱신

### Idle 발화 후

- 유저가 응답하면 `last_user_message_at` 갱신으로 자연스럽게 타이머 리셋
- 무응답이면 쿨다운 때문에 재발화 방지
- 향후 확장: 반복 타이머(B), 조건부 타이머(C)는 TODO로 명시

## Phase 2: 시간 기반 트리거

### ScheduleManager 동작

1. `services.yml`에 스케줄 정의
2. 서버 시작 시 APScheduler에 YAML 스케줄을 job으로 등록
3. Job 실행 시 `WebSocketManager`의 활성 connection 목록을 조회 (WS가 연결된 세션만 대상)
4. 각 connection의 session_id에 대해 `trigger_proactive(session_id, "scheduled")` 호출
5. 동일한 공통 실행 흐름 (lock -> 재확인 -> 쿨다운 -> agent -> push)

### 페르소나별 분기

- 프롬프트 템플릿은 `proactive_prompts.yml`에서 `prompt_key`로 로드
- 페르소나별로 다른 프롬프트가 필요하면 `personas.yml`에서 오버라이드

### 연결된 세션 없음

아무 일도 안 함 (no-op). 로그만 남김.

### 향후 확장

- 런타임 스케줄 CRUD API (`YAML 기본값 + API 오버라이드`)는 TODO로 명시

## Phase 3: Webhook 트리거

### Endpoint

```
POST /v1/proactive/trigger
{
  "session_id": "uuid-string",
  "trigger_type": "webhook",
  "prompt_key": "custom_alert",    // optional, 없으면 기본 webhook 프롬프트
  "context": "서버 점검 10분 전"    // optional, 프롬프트에 주입할 추가 컨텍스트
}
```

### 동작

1. `session_id`로 활성 connection 조회 -> 없으면 404
2. `trigger_proactive(session_id, "webhook", prompt_key, context)` 호출
3. 동일한 공통 실행 흐름
4. 응답: `{"status": "triggered", "turn_id": "..."}` 또는 `{"status": "skipped", "reason": "session_locked"}`

### 인증

없음. 내부 네트워크 전제 (NanoClaw 콜백과 동일 패턴).

## Client Message Tagging

기존 WS 메시지 포맷에 `"proactive": true` 메타데이터를 추가한다.

- 스트리밍 이벤트(`stream_start`, `stream_token`, `tts_chunk`)는 plain dict -> json.dumps 경로로 전송되므로 필드 추가가 자유로움
- 기존 클라이언트(Unity, JS)는 모르는 필드를 silently ignore -> 하위 호환성 유지
- `StreamStartMessage` Pydantic 모델에 `proactive: bool | None = None` 추가하여 모델 레벨 정합성 유지

## Configuration

### services.yml 추가 섹션

```yaml
proactive:
  idle_timeout_seconds: 300       # 기본 5분
  cooldown_seconds: 600           # 발화 후 10분 쿨다운
  watcher_interval_seconds: 30    # IdleWatcher 체크 주기
  schedules:
    - id: morning_greeting
      cron: "0 9 * * *"
      prompt_key: morning
      enabled: true
```

### personas.yml 오버라이드

```yaml
personas:
  yuri:
    idle_timeout_seconds: 180     # 유리는 3분만에 말 걸기
```

### proactive_prompts.yml

```yaml
idle: |
  유저가 {idle_seconds}초 동안 조용합니다.
  현재 시각은 {current_time}입니다.
  자연스럽게 말을 걸어주세요.

morning: |
  현재 시각은 {current_time}입니다.
  아침 인사를 해주세요.

webhook: |
  외부 트리거가 발생했습니다.
  컨텍스트: {context}
  이 상황에 맞게 유저에게 알려주세요.
```

템플릿 변수: `{idle_seconds}`, `{current_time}`, `{context}` 등을 `str.format()`으로 치환.

## Testing Strategy

### Unit Tests

- `IdleWatcher`: idle 감지 로직, timeout 계산, 페르소나별 오버라이드 적용
- `ProactiveService.trigger_proactive()`: lock 실패 시 취소, idle 재확인 취소, 쿨다운 취소, 정상 트리거
- `PromptLoader`: YAML 로드, 템플릿 변수 치환, 누락 키 처리
- `ScheduleManager`: 스케줄 등록/해제

### E2E Tests

- Phase 1: WS 연결 -> idle_timeout 대기 -> proactive 메시지 수신 확인 (`proactive: true` 태깅 검증)
- Phase 2: 짧은 cron 간격으로 스케줄 트리거 -> 메시지 수신 확인
- Phase 3: `POST /v1/proactive/trigger` -> WS로 메시지 수신 확인
- 충돌 방지: 유저 턴 진행 중 proactive 트리거 -> skip 확인
- 쿨다운: 연속 트리거 시 두 번째 skip 확인

### E2E Config

`services.e2e.yml`에 짧은 timeout:
```yaml
proactive:
  idle_timeout_seconds: 3
  cooldown_seconds: 5
  watcher_interval_seconds: 1
```

## Future TODOs

- [ ] Idle 트리거 반복 모드 (유저 무응답 시 주기적 발화)
- [ ] Idle 트리거 조건부 모드 (시간대, 세션 상태 등 조건 추가)
- [ ] 런타임 스케줄 CRUD API (YAML 기본값 + API 오버라이드)
- [ ] Webhook 인증 (API key 헤더 + rate limit)
- [ ] Broadcast 모드 (session_id 없이 전체 활성 세션에 발화)
- [ ] EventBus 기반 아키텍처 전환 (trigger_proactive() 시그니처가 곧 이벤트 페이로드이므로 자연스럽게 마이그레이션 가능)
