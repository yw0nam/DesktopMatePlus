# TODO

## Phase 1 — CI/CD & Safety Net

- [x] GitHub Actions CI 워크플로우 추가 (PR 트리거: lint + pytest + coverage report) `cc:DONE`
- [x] pre-commit 훅 정상화 — .pre-commit-config.yaml에서 ruff/black 주석 해제 `cc:DONE`
- [x] pyproject.toml에 [tool.coverage] 섹션 추가 (source, omit, threshold) `cc:DONE`

## Phase 2 — Developer Experience

- [x] Makefile 추가 (make lint, make test, make e2e, make run) `cc:DONE`
- [x] Dockerfile + docker-compose 추가 (MongoDB + Qdrant + Neo4j + backend 원커맨드 기동) `cc:DONE`

## Phase 3 — Error Handling & Observability

- [x] _shutdown() 보완 — MongoDB, Agent, TTS, WebSocket 커넥션 정리 추가 `cc:DONE`
- [x] ErrorClassifier 패턴을 서비스 초기화/헬스체크에 확산 (현재 WebSocket만 적용) `cc:DONE`

## Phase 4 — Config 정리

- [ ] main.py의 channel/sweep 인라인 YAML 파싱을 service_manager 패턴으로 통일 `cc:TODO`
