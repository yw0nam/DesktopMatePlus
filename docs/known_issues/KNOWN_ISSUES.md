# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

---

## Backend (`backend/`)

- [ ] **KI-1** [Medium] config: `yaml_files/services/tts_service/irodori.yml`의 `base_url`이 로컬 IP(`192.168.0.41:8091`)로 하드코딩됨 — GP-4 위반. 환경변수 또는 설정 오버라이드로 교체 필요.
- [ ] **KI-2** [Low] architecture: 6개 서비스 파일이 200줄 초과 — 단일 책임 원칙 위반. processor.py(626L), event_handlers.py(448L), websocket_manager.py(438L), service_manager.py(412L), handlers.py(386L), openai_chat_agent.py(333L). 각 파일을 기능 단위로 분리 필요. → 상세 파일 없음 (인라인 기록)
- [ ] **KI-3** [Low] security: `handlers.py:52` validate_token()이 항상 `"valid_token"` 반환 — 개인 시스템이므로 YAGNI. 멀티유저 전환 시 실제 인증 로직 필요.

## PR #19 (`feat/devex`) — DevEx

- [ ] **KI-4** [Medium] docker: Dockerfile이 root로 실행됨 — 프로덕션/공유 환경 배포 전 non-root USER 추가 필요.
- [ ] **KI-5** [Medium] docker: `host.docker.internal`이 Linux 네이티브 Docker에서 기본 미지원 — `docker-compose.yml` backend 서비스에 `extra_hosts: ["host.docker.internal:host-gateway"]` 추가 필요.

## PR #20 (`feat/error-handling`) — Error Handling

- [ ] **KI-6** [Medium] channel: `SlackService.cleanup()`이 `AsyncWebClient.close()` 호출하나 해당 메서드 미존재 — try/except으로 안전하나 실제 cleanup 안 됨. `self._client.session.close()` 방식으로 교체 필요.
- [ ] **KI-7** [Low] health: `_severity()` 함수가 에러 문자열 키워드 매칭으로 severity 분류 — 실제 exception 타입 기반 분류로 개선 권장.
