# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

> 해결된 이슈는 `docs/release_notes/`에 보관됩니다.

---

## Open Issues

### PR #25–#27 (`feat/phase6*`) — Builtin Tools / MCP / ToolGate

- [ ] **KI-16** [Low] docker: `openai_chat_agent.yml`이 Docker/로컬 공유 — `tool_config.builtin.filesystem.root_dir: /tmp/agent-workspace`가 Docker에서 ephemeral (컨테이너 재시작 시 소멸). 현재 `enabled: false`라 미발현. **해결 방향: filesystem tool 활성화 PR에서 `openai_chat_agent.docker.yml` 분리 + `docker.yml` 참조 변경 + `docker-compose.yml`에 named volume 추가 + `src/configs/agent/openai_chat_agent.py:27` Pydantic 기본값 수정.** (방법 B env var interpolation은 YAML 로더 cross-cutting 변경 필요로 reject)

---

### `feat/human_in_the_loop` — HitL Gate

- [ ] **KI-22** [Low] test: `tests/e2e/test_hitl_e2e.py::TestHitLExistingFlowUnchanged::test_safe_tool_no_hitl_request` E2E 테스트가 비결정적 — LLM이 의도한 빌트인 `search_memory` 대신 위험 MCP 툴을 선택할 경우 `pytest.skip()`으로 처리됨. 안전 툴의 HitL 게이트 우회를 E2E 수준에서 신뢰성 있게 검증하지 못함. **단위 테스트 커버리지 충분**: `test_hitl_middleware.py::test_safe_tool_passes_through`, `test_builtin_tool_is_safe`가 결정론적으로 동일 로직을 검증함. **해결 방향: skip 패턴을 LLM 비결정성의 내재적 한계로 수용하거나, MCP 툴 없이 에이전트를 초기화하는 전용 E2E 픽스처를 추가해 safe-tool-only 경로를 강제함.**

---

### FE emotion tag rendering Issue

- [ ] **KI-23** [Low] FE rendering: Emotion이 Unity FE에서 깨짐. stream token으로 FE에 쏠때, emotion tag를 삭제후 token을 쏴야함.

---


### PR #38 (`feat/proactive-talking`) — Proactive Talking

- [ ] **KI-24** [Low] proactive: `IdleWatcher.scan_once()`가 idle connection을 순차 처리 — `trigger_proactive()` 완료까지 다음 connection 처리 차단. 현재 데스크톱 앱 단일 유저라 미발현. **해결 방향: `asyncio.create_task`로 trigger를 비동기 dispatch하여 connection 간 blocking 제거.**
- [ ] **KI-25** [Low] proactive: `ScheduleManager._on_schedule_fire()`가 활성 connection에 순차 broadcast — 동일 원인. **해결 방향: `asyncio.gather`로 동시 broadcast.**

---

## Resolved Issues

| Issue | PR | Summary | Resolution |
|-------|-----|---------|------------|
| KI-18 | #30 | E2E 테스트 시 MongoDB 세션 누적 | `stm_session` fixture를 `yield` + teardown `DELETE`로 수정 |
| KI-19 | #28 | `_ConcreteAgent.stream` 타입 시그니처 불일치 | `return` 제거, bare `yield`만 남겨 async generator로 수정 |
| KI-20 | #28 | `/health` severity 직렬화 검증 부재 | `ErrorSeverity` enum 사용, `"severity" in module` assertion 추가 |
| KI-21 | #29 | `scripts/run.sh` YAML 경로 참조 우려 | Won't Fix — 실제 미발현 확인 |

---

## Won't Fix

| Issue | Reason |
|-------|--------|
| KI-2 | 6개 서비스 파일 200줄 초과 — YAGNI, 억지 분리 시 가독성 저하 |
| KI-3 | `validate_token()` 항상 `"valid_token"` — 개인 시스템이므로 YAGNI |
| KI-7 | `_severity()` 문자열 키워드 매칭 — 현재 정상 동작 |
| KI-11 | `RestrictedShellTool` cwd 제한 없음 — Docker 샌드박스로 충분 |
