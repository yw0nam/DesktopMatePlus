# Channel Service — Patterns & Conventions

Updated: 2026-03-25

> **Data Flow:** [SLACK_MESSAGE](../../../../docs/data_flow/channel/SLACK_MESSAGE.md) — 전체 메시지 처리 시퀀스 다이어그램

- **`process_message()` 공통 진입점:** Webhook 라우트(text 있음)와 Callback 핸들러(text="") 양쪽에서 호출. `text=""`이면 STM에 TaskResult가 이미 주입된 상태이므로 `HumanMessage` 추가하지 않음.

- **`session_lock`:** `cachetools.TTLCache` 기반, 10분 TTL, maxsize 1024. 동일 세션의 동시 처리 방지.
- **`reply_channel` 메타데이터:** `process_message()`가 STM session metadata에 `{"provider": "slack", "channel_id": "..."}` 형태로 저장. `callback.py`는 이 값을 읽어 Slack 라우팅 결정.
- **`init_channel_service()`는 async:** lifespan에서 `await init_channel_service(slack_settings)` 로 호출.
- **`SlackService` 서명 검증:** HMAC-SHA256, 5분 타임스탬프 tolerance, `hmac.compare_digest` 사용.
- **`SlackService.initialize()`:** 비동기. `auth.test`로 봇 user_id 조회 → `_bot_user_id` 저장. 실패 시 경고만 기록하고 이름 기반 매칭으로 폴백 (논-파탈).
- **`parse_event()` mention 필터링:** DM 채널('D'로 시작)은 항상 응답; 공개/그룹 채널은 `@bot_name` 또는 `<@BOT_USER_ID>` mention 필요. mention은 에이전트에 전달 전 텍스트에서 제거됨.
- **session_id 형식:** `"slack:{team_id}:{channel_id}:{user_id}"` (현재 user_id는 `"default"` 상수).
- **`upsert_session`:** filter는 `session_id`만 사용, `user_id`/`agent_id`는 `$set`으로 업데이트. `add_chat_history`와 달리 메시지 미삽입.
- **`BackgroundSweepService`:** `slack_service_fn: Callable[[], SlackService | None]` lazy 주입으로 초기화 순서 의존 없음.
