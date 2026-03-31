# Release Notes - Backend Code Improvements

Updated: 2026-03-07

## [feat/improvement_code] (2026-03-07)

> Bug fixes and design improvements identified during code review. No breaking changes for external clients.

### Bug Fixes

* **[P0] 이벤트 루프 블로킹 해소** (`openai_chat_agent.py`)
  - `save_memory()` 동기 호출 → `asyncio.create_task(save_memory(...))` fire-and-forget으로 교체.
  - 메모리 저장 중 모든 WebSocket 연결이 멈추는 문제 해소.

* **[P0] LTM TOCTOU + 무한 반복 트리거 수정** (`service.py`)
  - `len(history) % batch_size == 0` 단순 modulo 방식 폐기.
  - STM `session.metadata.ltm_last_consolidated_at_turn`을 기준으로 `current_turn - last >= N` 조건으로 교체.
  - 동시 요청 시 중복 consolidation 방지 및 20/40/60... 매번 트리거 방지.

### Design Improvements

* **[P1] `turn_id` / `session_id` / `thread_id` 시맨틱 분리** (`openai_chat_agent.py`)
  - 기존: `run_id` 하나가 LangGraph `thread_id`, WebSocket `turn_id`, 반환 `session_id` 역할을 혼용.
  - 변경: `turn_id` (클라이언트 이벤트용), `thread_id` (LangGraph 내부), `session_id` (영속 세션) 명확히 분리.
  - `session_id`를 `save_memory()` 반환값으로 덮어쓰던 코드 제거.

* **[P1] `_config_paths` 글로벌 제거** (`main.py`)
  - 모듈 레벨 mutable global dict 삭제.
  - `create_app(config_paths)` 파라미터로 전달, `lifespan`이 클로저로 캡처.

* **[P1] `WeakSet` → `set` 교체** (`websocket_manager.py`)
  - `self._heartbeat_tasks: WeakSet` → `set[asyncio.Task]`로 교체.
  - 완료된 태스크는 `task.add_done_callback(self._heartbeat_tasks.discard)` 로 즉시 제거.
  - shutdown 시 명시적 `task.cancel()` 가능.

### Code Quality

* **[P2] 동기 `save_memory` 삭제** (`service.py`)
  - 사용처 없어진 sync 버전 삭제, `async_save_memory` → `save_memory`로 rename.

* **[P2] 버퍼 flush 4중 반복 → `_flush_buffer()` 헬퍼** (`openai_chat_agent.py`)
  - `node == "tools"` / `node == "agent"` 분기가 4개 위치에 반복 → `_flush_buffer(node, buffer)` static method로 추출.

### New Features

* **`STMService.get_session_metadata(session_id) -> dict`** (`stm_service/service.py`, `stm_service/mongodb.py`)
  - LTM consolidation tracking을 위해 신규 추가.
  - 세션 없으면 `{}` 반환 (예외 미발생).

### Testing

All tests passing (215 passed, 7 skipped):

```bash
uv run pytest tests/ -q
```

### Related Documents

* [Agent Service](../feature/service/Agent_Service.md)
* [STM Service](../feature/service/STM_Service.md)
* [Improvement PRD](../prds/improvements/BACKEND_IMPROVEMENTS.md)
