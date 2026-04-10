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

## Phase 5 — Known Issues 정리

- [x] KI-1: irodori.yml `base_url` 하드코딩 → 환경변수 오버라이드 `cc:DONE`
- [x] KI-4: Dockerfile non-root USER 추가 `cc:DONE`
- [x] KI-5: docker-compose.yml에 `extra_hosts: ["host.docker.internal:host-gateway"]` 추가 `cc:DONE`
- [x] KI-6: SlackService.cleanup() → `self._client.session.close()` 수정 `cc:DONE`

## Phase 6 — Agent Skill/Tool 확장

- [ ] `desktopmate_skills/` 폴더 구조 설계 — YAML 기반 skill/workflow 정의 체계 `cc:TODO`
- [ ] LangGraph skill injection — startup 시 skills 폴더 스캔 → tool registry → agent 주입 `cc:TODO`
- [ ] MCP filesystem 서버 연결 — 공식 `modelcontextprotocol/servers/filesystem` (path allowlist 샌드박스) `cc:TODO`
- [ ] MCP computer-control 서버 연결 — `computer-control-mcp` (PyAutoGUI: 마우스/키보드/스크린샷/OCR) `cc:TODO`
- [ ] OS 프로세스 목록 접근 — MCP shell-exec 또는 커스텀 tool `cc:TODO`
- [ ] MCP code-sandbox 서버 연결 — Docker 기반 Python/shell 실행 환경 (`code-sandbox-mcp`) `cc:TODO`

## Phase 7 — 대화 품질 개선

- [ ] 유저 컨텍스트 프로필 — 유저 직업/관심사/일정 등 구조화 저장, 개인화 대화 `cc:TODO`
- [ ] 대화 요약/다이제스트 — 일정 턴 후 STM 자동 압축, 컨텍스트 윈도우 절약 `cc:TODO`

## Phase 6 Idea — 중간 에이전트 레이어 (추후 필요 시 추가)

> Agent 응답 시간 목표: ≤0.5초. code-sandbox 실행이 이 제약을 넘는 태스크가 반복되면
> claude code/opencode 같은 코딩 에이전트를 MCP로 연결하여 비동기 위임하는 중간 레이어 검토.
> NanoClaw delegation과 역할 경계 정리 필요 (NanoClaw = 무거운 장기 작업, 중간 에이전트 = 수 초~수십 초 자율 추론).

## Phase 8 — 스케줄/리마인더 (검토 필요)

- [ ] 스케줄/리마인더 시스템 — cron 기반 예약 메시지 ("3시에 알려줘") `cc:TODO`
- [ ] 감정 상태 트래킹 — 대화 감정 분석 → 캐릭터 반응 조절 `cc:TODO`
- [ ] 데스크톱 통합 트리거 — backend는 트리거/데이터 제공, 실제 OS 연동은 DH MOD 담당 `cc:TODO`
