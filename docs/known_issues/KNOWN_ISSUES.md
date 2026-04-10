# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

---

## Backend (`backend/`)

- [x] **KI-1** [Medium] config: `IRODORI_TTS_BASE_URL` 환경변수 오버라이드 추가 — `tts_config.type == 'irodori'`일 때만 적용 (#21)
- [ ] **KI-2** [Low] architecture: 6개 서비스 파일이 200줄 초과 — 단일 책임 원칙 위반. processor.py(626L), event_handlers.py(448L), websocket_manager.py(438L), service_manager.py(412L), handlers.py(386L), openai_chat_agent.py(333L). 각 파일을 기능 단위로 분리 필요. → 상세 파일 없음 (인라인 기록)
- [ ] **KI-3** [Low] security: `handlers.py:52` validate_token()이 항상 `"valid_token"` 반환 — 개인 시스템이므로 YAGNI. 멀티유저 전환 시 실제 인증 로직 필요.

## PR #19 (`feat/devex`) — DevEx

- [x] **KI-4** [Medium] docker: Dockerfile에 non-root `appuser` 추가 및 `/app` 소유권 설정 (#21)
- [x] **KI-5** [Medium] docker: `docker-compose.yml` backend 서비스에 `extra_hosts: ["host.docker.internal:host-gateway"]` 추가 — 이미 반영됨

## PR #19 (`feat/devex`) — DevEx (추가)

- [ ] **KI-8** [Low] docker: `mongo:7` floating major tag — 마이너 버전 고정 권장 (`mongo:7.0`).
- [ ] **KI-9** [Low] docker: `mem0.docker.yml`의 `neo4j graph_store`가 `bolt://localhost:7687` 하드코딩 — Docker 환경에서 미작동할 수 있음, 경고 주석 또는 env 오버라이드 필요.

## PR #20 (`feat/error-handling`) — Error Handling

- [x] **KI-6** [Medium] channel: `SlackService.cleanup()` → `getattr + not session.closed` 패턴으로 교체 완료 (#21)
- [ ] **KI-7** [Low] health: `_severity()` 함수가 에러 문자열 키워드 매칭으로 severity 분류 — 실제 exception 타입 기반 분류로 개선 권장.
- [ ] **KI-10** [Low] health: `ModuleStatus.severity` 타입이 `str | None` — `ErrorSeverity | None`으로 교체하면 타입 안전성 향상.
