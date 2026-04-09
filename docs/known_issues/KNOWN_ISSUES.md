# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

---

## Backend (`backend/`)

- [ ] **KI-1** [Medium] config: `yaml_files/services/tts_service/irodori.yml`의 `base_url`이 로컬 IP(`192.168.0.41:8091`)로 하드코딩됨 — GP-4 위반. 환경변수 또는 설정 오버라이드로 교체 필요.
- [ ] **KI-2** [Low] architecture: 6개 서비스 파일이 200줄 초과 — 단일 책임 원칙 위반. processor.py(626L), event_handlers.py(448L), websocket_manager.py(438L), service_manager.py(412L), handlers.py(386L), openai_chat_agent.py(333L). 각 파일을 기능 단위로 분리 필요. → 상세 파일 없음 (인라인 기록)
- [ ] **KI-3** [Low] security: `handlers.py:52` validate_token()이 항상 `"valid_token"` 반환 — 개인 시스템이므로 YAGNI. 멀티유저 전환 시 실제 인증 로직 필요.
