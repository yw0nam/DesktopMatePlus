# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

---

## Backend (`backend/`)

- [x] **KI-1** [Medium] config: `IRODORI_TTS_BASE_URL` 환경변수 오버라이드 추가 — `tts_config.type == 'irodori'`일 때만 적용 (#21)
- [x] **KI-2** [Low] architecture: 6개 서비스 파일이 200줄 초과 — YAGNI. 현재 동작에 문제 없고 억지 분리 시 오히려 가독성 저하. 추후 기능 추가/변경 시 자연스럽게 분리 검토. Won't fix.
- [X] **KI-3** [Low] security: `handlers.py:52` validate_token()이 항상 `"valid_token"` 반환 — 개인 시스템이므로 YAGNI. 멀티유저 전환 시 실제 인증 로직 필요. 현재는 하드코딩된 토큰으로 간단히 보호하는 형태 유지. Won't fix.

## PR #19 (`feat/devex`) — DevEx

- [x] **KI-4** [Medium] docker: Dockerfile에 non-root `appuser` 추가 및 `/app` 소유권 설정 (#21)
- [x] **KI-5** [Medium] docker: `docker-compose.yml` backend 서비스에 `extra_hosts: ["host.docker.internal:host-gateway"]` 추가 — 이미 반영됨

## PR #19 (`feat/devex`) — DevEx (추가)

- [x] **KI-8** [Low] docker: `mongo:7` floating major tag — `mongo:7.0`으로 고정 완료.
- [x] **KI-9** [Low] docker: `mem0.docker.yml`의 `neo4j graph_store` — `bolt://neo4j:7687` (compose 서비스명)으로 수정 완료, env override 주석 추가됨.

## PR #20 (`feat/error-handling`) — Error Handling

- [x] **KI-6** [Medium] channel: `SlackService.cleanup()` → `getattr + not session.closed` 패턴으로 교체 완료 (#21)
- [x] **KI-7** [Low] health: `_severity()` 함수가 에러 문자열 키워드 매칭으로 severity 분류 — YAGNI. 현재 정상 동작하며 확장 예정 없음. 추후 문제 발생 시 exception 타입 기반으로 전환. Won't fix.
- [x] **KI-10** [Low] health: `ModuleStatus.severity` 타입이 `str | None` — `ErrorSeverity | None`으로 교체하여 타입 안전성 향상 (#28)

## PR #25 (`feat/phase6a-builtin-tools`) — Builtin Tools

- [x] **KI-11** [Medium] shell: `RestrictedShellTool`에 `cwd` 제한 없음 — Docker 컨테이너 자체가 샌드박스이므로 컨테이너 내 `cwd` 제한은 과잉 방어. 화이트리스트 + `shell=False` + 메타문자 차단으로 충분. Won't fix.
- [x] **KI-12** [Low] logging: `ToolRegistry`와 개별 tool factory (`get_filesystem_tools` 등)에서 중복 로깅 발생 — registry 레벨에서만 로깅하도록 정리 (#28)

## PR #26 (`feat/phase6b-mcp-sandbox`) — MCP Lifecycle

- [x] **KI-13** [Medium] agent: `cleanup_async()`가 `OpenAIChatAgent`에만 정의 — base `AgentService` 클래스에 default no-op 추가하고 `main.py`의 `hasattr` 가드 제거 (#28)
- [X] **KI-14** [Low] yaml: MCP config 예시의 `npx -y @modelcontextprotocol/server-sequential-thinking` 버전 미고정 — 마이너 버전 핀 권장. -> 예시일뿐, 실제로는 안쓸거임. 삭제

## PR #24 (`refactor/phase4-config-unify`) — Config Unify

- [x] **KI-15** [Low] imports: `initialize_channel_service()` 내 `import os` 로컬 임포트가 모듈 레벨 임포트와 중복 — 로컬 임포트 제거 (#28)

## PR #25–#27 (`feat/phase6*`) — Builtin Tools / MCP / ToolGate

- [ ] **KI-16** [Low] docker: `openai_chat_agent.yml`이 Docker/로컬 공유 — `tool_config.builtin.filesystem.root_dir: /tmp/agent-workspace`가 Docker에서 ephemeral (컨테이너 재시작 시 소멸). 현재 `enabled: false`라 미발현. **해결 방향: filesystem tool 활성화 PR에서 `openai_chat_agent.docker.yml` 분리 + `docker.yml` 참조 변경 + `docker-compose.yml`에 named volume 추가 + `src/configs/agent/openai_chat_agent.py:27` Pydantic 기본값 수정.** (방법 B env var interpolation은 YAML 로더 cross-cutting 변경 필요로 reject)

## PR #28 (`refactor/ki-batch-fix`) — Review Findings

- [ ] **KI-19** [Low] test: `test_agent_service_base.py`의 `_ConcreteAgent.stream` 메서드가 `AgentService.stream` 추상 메서드와 타입 시그니처 불일치 — 테스트에서 `yield`로 async generator를 반환하지만 실제 구현체는 코루틴/제너레이터 혼합 패턴. 타입 체커(basedpyright)에서 `reportIncompatibleMethodOverride` 경고. **해결 방향: 테스트 클래스의 `stream` 메서드를 실제 구현체와 동일한 패턴으로 수정하거나, `@abstractmethod`가 아닌 concrete no-op으로 변경 검토.**
- [ ] **KI-20** [Low] test: `/health` 엔드포인트의 `ModuleStatus.severity` 직렬화 검증 부재 — `ErrorSeverity` StrEnum이 JSON 응답에서 문자열로 직렬화되는지 API 레벨 테스트 없음. 현재는 단위 테스트만 존재. **해결 방향: `test_health.py` 또는 `test_real_e2e.py`에 `severity` 필드가 `"transient" | "recoverable" | "fatal"` 중 하나인지 검증하는 assertion 추가.**

## PR #29 (`refactor/yaml-config-unify`) — Review Findings

- [ ] **KI-21** [Low] scripts: `scripts/run.sh`가 삭제된 YAML 경로 참조 — `yaml_files/services/checkpointer.yml`, `yaml_files/services/ltm_service/mem0.yml` 등 삭제된 경로를 `_read_mongo_uri()`, `_read_qdrant_url()`에서 참조. PR #29에서 수정되지 않아 preflight check가 묵시적으로 skip됨. **해결 방향: `run.sh`의 helper 함수들이 `services.yml`을 읽도록 수정.**
- [x] **KI-22** [Low] config: `yaml_files/services/knowledge_base.yaml` 삭제 — 통합 설정 파일에 미포함. `KnowledgeBaseService`는 코드상 존재하나 설정 로드 경로 없음. 현재 런타임에 영향 없음 (초기화되지 않는 서비스). **판정: 미사용 설정으로 안전 삭제, 추후 해당 서비스 활성화 시 `services.yml`에 추가.**

## `refactor/yaml-config-unify` — Callback / STM

- [ ] **KI-17** [Medium] architecture: `pending_tasks`가 LangGraph checkpointer state에 종속 — 모델 추론에 미사용(bookkeeping 전용)임에도 LangGraph state 필드로 관리됨. `as_node="model"` 필수, `_ALLOWED_METADATA_KEYS` whitelist 관리 필요, agent service 미초기화 시 읽기/쓰기 불가 등 coupling 발생. **해결 방향: `pending_tasks`를 별도 MongoDB 컬렉션으로 분리하고 callback/delegate/sweep이 직접 읽기/쓰기하도록 리팩토링.**
- [ ] **KI-18** [Low] test: E2E 테스트 실행 시 MongoDB에 테스트 세션이 누적됨 — `e2e-test-user` / `e2e-test-agent` prefix 세션이 LangGraph checkpointer 및 session_registry에 잔류. 누적된 세션은 `task_sweep_service`가 불필요한 aupdate_state를 시도해 ERROR 로그를 발생시킴. **해결 방향: E2E 테스트 teardown(fixture `yield` 이후 또는 conftest `autouse` session-scoped fixture)에서 생성된 세션을 `DELETE /v1/stm/sessions/{sid}`로 삭제.**

---

## PatchNote

**2026-04-13**: PR #28, #29 리뷰 완료 및 KNOWN_ISSUES 업데이트
- KI-10, KI-12, KI-13, KI-15 완료 표시 (#28에서 해결)
- KI-19 ~ KI-22 신규 추가 (리뷰 발견 이슈)
