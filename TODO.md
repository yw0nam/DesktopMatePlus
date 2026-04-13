# TODO

## CI/CD & Safety Net (2026-04-08)

- [x] GitHub Actions CI 워크플로우 추가 (PR 트리거: lint + pytest + coverage report) `cc:DONE`
- [x] pre-commit 훅 정상화 — .pre-commit-config.yaml에서 ruff/black 주석 해제 `cc:DONE`
- [x] pyproject.toml에 [tool.coverage] 섹션 추가 (source, omit, threshold) `cc:DONE`

## Developer Experience (2026-04-09)

- [x] Makefile 추가 (make lint, make test, make e2e, make run) `cc:DONE`
- [x] Dockerfile + docker-compose 추가 (MongoDB + Qdrant + Neo4j + backend 원커맨드 기동) `cc:DONE`

## Error Handling & Observability (2026-04-10)

- [x] _shutdown() 보완 — MongoDB, Agent, TTS, WebSocket 커넥션 정리 추가 `cc:DONE`
- [x] ErrorClassifier 패턴을 서비스 초기화/헬스체크에 확산 (현재 WebSocket만 적용) `cc:DONE`

## Config 정리 (2026-04-10)

- [x] channel/sweep 초기화를 `_load_service_yaml()` 공통 헬퍼로 통일 `cc:DONE`

## Known Issues 정리 (2026-04-10)

- [x] KI-1: irodori.yml `base_url` 하드코딩 → 환경변수 오버라이드 `cc:DONE`
- [x] KI-4: Dockerfile non-root USER 추가 `cc:DONE`
- [x] KI-5: docker-compose.yml에 `extra_hosts: ["host.docker.internal:host-gateway"]` 추가 `cc:DONE`
- [x] KI-6: SlackService.cleanup() → `self._client.session.close()` 수정 `cc:DONE`

## Agent Skill/Tool 확장 (2026-04-11)

### 빌트인 Tool + Registry (2026-04-11)

- [x] Tool Registry (`tools/registry.py`) — YAML config 기반 tool 활성화/비활성화 `cc:DONE`
- [x] LangChain 빌트인 tool 등록 — FileSystem, Shell(화이트리스트), DuckDuckGoSearch `cc:DONE`
- [x] `openai_chat_agent.py` initialize_async에서 registry 사용하도록 변경 `cc:DONE`

### MCP 서버 연결 (2026-04-11)

- [ ] MCP code-sandbox 서버 연결 — `pydantic/mcp-run-python` (Docker 격리) `cc:TODO`
- [x] MultiServerMCPClient 라이프사이클 보강 — stateless 패턴 + cleanup_async `cc:DONE`

### Tool Gating Middleware (2026-04-11)

- [x] `tool_gate_middleware.py` — wrap_tool_call 패턴, Shell 화이트리스트/filesystem path 범위 체크 `cc:DONE`

## 대화 품질 개선 (2026-04-11)

- [x] 유저 컨텍스트 프로필 — 유저 직업/관심사/일정 등 구조화 저장, 개인화 대화 `cc:DONE`
- [x] 대화 요약/다이제스트 — 일정 턴 후 STM 자동 압축, 컨텍스트 윈도우 절약 `cc:DONE`

## Idea — 중간 에이전트 레이어 (2026-04-11 추후 필요 시 추가)

> Agent 응답 시간 목표: ≤0.5초. code-sandbox 실행이 이 제약을 넘는 태스크가 반복되면
> claude code/opencode 같은 코딩 에이전트를 MCP로 연결하여 비동기 위임하는 중간 레이어 검토.
> NanoClaw delegation과 역할 경계 정리 필요 (NanoClaw = 무거운 장기 작업, 중간 에이전트 = 수 초~수십 초 자율 추론).

## Known Issues 정리 (2026-04-13)

### Medium Priority

- [x] KI-11: Docker 샌드박스로 충분 — Won't fix `cc:DONE`
- [ ] KI-13: `cleanup_async()` base `AgentService`에 default no-op 추가, `main.py` `hasattr` 가드 제거 `cc:TODO`

### Low Priority (Quick-win batch)

- [ ] KI-10: `ModuleStatus.severity` 타입 `str | None` → `ErrorSeverity | None` 교체 `cc:TODO`
- [ ] KI-12: ToolRegistry/tool factory 중복 로깅 정리 — registry 레벨에서만 로깅 `cc:TODO`
- [x] KI-14: MCP config `npx -y @modelcontextprotocol/server-sequential-thinking` -> 삭제할거임, 따라서 필요없음`cc:DONE`
- [ ] KI-15: `initialize_channel_service()` 내 `import os` 로컬 임포트 중복 제거 `cc:TODO`

## YAML 설정 통합 (2026-04-13)

- [ ] `yaml_files/services/` 하위 파편화된 YAML을 `services.yml` / `services.docker.yml` / `services.e2e.yml`로 통합 `cc:TODO`
- [ ] YAML 로더 코드(`src/configs/`) 통합 구조에 맞게 수정 `cc:TODO`
- [ ] `main.yml` / `docker.yml` 참조 경로 업데이트 `cc:TODO`
- [ ] `e2e.sh`에서 `YAML_FILE=yaml_files/services.e2e.yml` 자동 설정 `cc:TODO`
- [ ] Docker mongo 인증 불일치 해소 — e2e용 connection_string에 인증 없는 `localhost:27017` 사용 `cc:TODO`

## 스케줄/리마인더 (검토 필요)

- [ ] 스케줄/리마인더 시스템 — cron 기반 예약 메시지 ("3시에 알려줘") `cc:TODO`
- [ ] 감정 상태 트래킹 — 대화 감정 분석 → 캐릭터 반응 조절 `cc:TODO`
- [ ] 데스크톱 통합 트리거 — backend는 트리거/데이터 제공, 실제 OS 연동은 DH MOD 담당 `cc:TODO`
