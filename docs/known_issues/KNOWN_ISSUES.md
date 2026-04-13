# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

> 해결된 이슈는 `docs/release_notes/`에 보관됩니다.

---

## Open Issues

### PR #25–#27 (`feat/phase6*`) — Builtin Tools / MCP / ToolGate

- [ ] **KI-16** [Low] docker: `openai_chat_agent.yml`이 Docker/로컬 공유 — `tool_config.builtin.filesystem.root_dir: /tmp/agent-workspace`가 Docker에서 ephemeral (컨테이너 재시작 시 소멸). 현재 `enabled: false`라 미발현. **해결 방향: filesystem tool 활성화 PR에서 `openai_chat_agent.docker.yml` 분리 + `docker.yml` 참조 변경 + `docker-compose.yml`에 named volume 추가 + `src/configs/agent/openai_chat_agent.py:27` Pydantic 기본값 수정.** (방법 B env var interpolation은 YAML 로더 cross-cutting 변경 필요로 reject)

### PR #28 (`refactor/ki-batch-fix`) — Review Findings

- [ ] **KI-19** [Low] test: `test_agent_service_base.py`의 `_ConcreteAgent.stream` 메서드가 `AgentService.stream` 추상 메서드와 타입 시그니처 불일치 — 테스트에서 `yield`로 async generator를 반환하지만 실제 구현체는 코루틴/제너레이터 혼합 패턴. 타입 체커(basedpyright)에서 `reportIncompatibleMethodOverride` 경고. **해결 방향: 테스트 클래스의 `stream` 메서드를 실제 구현체와 동일한 패턴으로 수정하거나, `@abstractmethod`가 아닌 concrete no-op으로 변경 검토.**
- [ ] **KI-20** [Low] test: `/health` 엔드포인트의 `ModuleStatus.severity` 직렬화 검증 부재 — `ErrorSeverity` StrEnum이 JSON 응답에서 문자열로 직렬화되는지 API 레벨 테스트 없음. 현재는 단위 테스트만 존재. **해결 방향: `test_health.py` 또는 `test_real_e2e.py`에 `severity` 필드가 `"transient" | "recoverable" | "fatal"` 중 하나인지 검증하는 assertion 추가.**

### PR #29 (`refactor/yaml-config-unify`) — Review Findings

- [ ] **KI-21** [Low] scripts: `scripts/run.sh`가 삭제된 YAML 경로 참조 — `yaml_files/services/checkpointer.yml`, `yaml_files/services/ltm_service/mem0.yml` 등 삭제된 경로를 `_read_mongo_uri()`, `_read_qdrant_url()`에서 참조. PR #29에서 수정되지 않아 preflight check가 묵시적으로 skip됨. **해결 방향: `run.sh`의 helper 함수들이 `services.yml`을 읽도록 수정.**

### PR #30 (`refactor/ki17-pending-tasks-mongodb`) — Callback / STM

- [ ] **KI-18** [Low] test: E2E 테스트 실행 시 MongoDB에 테스트 세션이 누적됨 — `e2e-test-user` / `e2e-test-agent` prefix 세션이 LangGraph checkpointer 및 session_registry에 잔류. 누적된 세션은 `task_sweep_service`가 불필요한 aupdate_state를 시도해 ERROR 로그를 발생시킴. **해결 방향: E2E 테스트 teardown(fixture `yield` 이후 또는 conftest `autouse` session-scoped fixture)에서 생성된 세션을 `DELETE /v1/stm/sessions/{sid}`로 삭제.**

---

## Won't Fix

| Issue | Reason |
|-------|--------|
| KI-2 | 6개 서비스 파일 200줄 초과 — YAGNI, 억지 분리 시 가독성 저하 |
| KI-3 | `validate_token()` 항상 `"valid_token"` — 개인 시스템이므로 YAGNI |
| KI-7 | `_severity()` 문자열 키워드 매칭 — 현재 정상 동작 |
| KI-11 | `RestrictedShellTool` cwd 제한 없음 — Docker 샌드박스로 충분 |
