# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

---

## Backend (`backend/`)

- [ ] **KI-1** [Medium] config: `yaml_files/services/tts_service/irodori.yml`의 `base_url`이 로컬 IP(`192.168.0.41:8091`)로 하드코딩됨 — GP-4 위반. 환경변수 또는 설정 오버라이드로 교체 필요.
