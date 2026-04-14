# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

> 해결된 이슈는 `docs/release_notes/`에 보관됩니다.

---

## Open Issues

### PR #25–#27 (`feat/phase6*`) — Builtin Tools / MCP / ToolGate

- [ ] **KI-16** [Low] docker: `openai_chat_agent.yml`이 Docker/로컬 공유 — `tool_config.builtin.filesystem.root_dir: /tmp/agent-workspace`가 Docker에서 ephemeral (컨테이너 재시작 시 소멸). 현재 `enabled: false`라 미발현. **해결 방향: filesystem tool 활성화 PR에서 `openai_chat_agent.docker.yml` 분리 + `docker.yml` 참조 변경 + `docker-compose.yml`에 named volume 추가 + `src/configs/agent/openai_chat_agent.py:27` Pydantic 기본값 수정.** (방법 B env var interpolation은 YAML 로더 cross-cutting 변경 필요로 reject)

### PR #28 (`refactor/ki-batch-fix`) — Review Findings

- [x] **KI-19** [Low] test: `test_agent_service_base.py`의 `_ConcreteAgent.stream` 메서드가 `AgentService.stream` 추상 메서드와 타입 시그니처 불일치 — 테스트에서 `yield`로 async generator를 반환하지만 실제 구현체는 코루틴/제너레이터 혼합 패턴. 타입 체커(basedpyright)에서 `reportIncompatibleMethodOverride` 경고. **해결: `return` 제거, bare `yield`만 남겨 정상적인 async generator로 수정 (refactor/ki-batch-cleanup).**
- [x] **KI-20** [Low] test: `/health` 엔드포인트의 `ModuleStatus.severity` 직렬화 검증 부재 — `ErrorSeverity` StrEnum이 JSON 응답에서 문자열로 직렬화되는지 API 레벨 테스트 없음. **해결: `test_health_endpoint.py`에 unhealthy mock에 severity 필드 추가 및 `"transient"|"recoverable"|"fatal"` assertion, 구조 테스트에 `"severity" in module` 추가 (refactor/ki-batch-cleanup).**

### PR #29 (`refactor/yaml-config-unify`) — Review Findings

- [x] **KI-21** [Low] scripts: `scripts/run.sh`가 삭제된 YAML 경로 참조 우려 — 탐색 결과 `run.sh`가 이미 `services.yml`을 정상 참조 중. 문제 없음 (Won't Fix — 실제 미발현 확인).

### PR #30 (`refactor/ki17-pending-tasks-mongodb`) — Callback / STM

- [x] **KI-18** [Low] test: E2E 테스트 실행 시 MongoDB에 테스트 세션이 누적됨 — `e2e-test-user` / `e2e-test-agent` prefix 세션이 LangGraph checkpointer 및 session_registry에 잔류. **해결: `stm_session` fixture를 `return` → `yield` + teardown `DELETE /v1/stm/sessions/{sid}` 호출로 수정 (refactor/ki-batch-cleanup).**

---

## Won't Fix

| Issue | Reason |
|-------|--------|
| KI-2 | 6개 서비스 파일 200줄 초과 — YAGNI, 억지 분리 시 가독성 저하 |
| KI-3 | `validate_token()` 항상 `"valid_token"` — 개인 시스템이므로 YAGNI |
| KI-7 | `_severity()` 문자열 키워드 매칭 — 현재 정상 동작 |
| KI-11 | `RestrictedShellTool` cwd 제한 없음 — Docker 샌드박스로 충분 |
