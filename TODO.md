# TODO

## Phase 1 — CI/CD & Safety Net

- [x] GitHub Actions CI 워크플로우 추가 (PR 트리거: lint + pytest + coverage report) `cc:DONE`
- [x] pre-commit 훅 정상화 — .pre-commit-config.yaml에서 ruff/black 주석 해제 `cc:DONE`
- [x] pyproject.toml에 [tool.coverage] 섹션 추가 (source, omit, threshold) `cc:DONE`

## Phase 2 — Tech Debt Tracking

- [ ] 코드 내 미추적 TODO 7건 KNOWN_ISSUES.md 등록 (health check, multi-emotion, multi-user, metadata filter 등) `cc:TODO`

## Phase 3 — Architecture Refactoring

- [ ] service_manager.py DI 리팩토링 — 6개 모듈 레벨 싱글턴을 ServiceRegistry 클래스로 통합 `cc:TODO`
- [ ] main.py lifespan 분리 — 서비스별 startup()/shutdown() 훅 정의, 200줄 모놀리스 해체 `cc:TODO`
- [ ] Config 관리 통합 — 3곳 분산 설정(settings.py, service_manager.py, main.py)을 Pydantic Settings + env var 오버라이드로 일원화 `cc:TODO`

## Phase 4 — Error Handling & Observability

- [ ] ErrorClassifier 패턴을 서비스 초기화/헬스체크에 확산 (현재 WebSocket만 적용) `cc:TODO`
- [ ] _shutdown() 보완 — MongoDB, Agent, TTS, WebSocket 커넥션 정리 추가 `cc:TODO`

## Phase 5 — Developer Experience

- [x] Makefile 추가 (make lint, make test, make e2e, make run) `cc:DONE`
- [x] Dockerfile + docker-compose 추가 (MongoDB + Qdrant + backend 원커맨드 기동) `cc:DONE`
