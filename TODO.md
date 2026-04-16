# TODO

> 완료된 작업은 `docs/release_notes/`에 보관됩니다.

## 기술 부채 관리

- [ ] TODO.md + KNOWN_ISSUES.md → GitHub Issues 통합 마이그레이션 — 기존 open 항목 전량 `gh issue create`로 이전, label 체계 수립 (`type:feature`/`type:tech-debt`, `severity:*`, `component:*`), 완료된 항목은 이전하지 않음, TODO.md + KNOWN_ISSUES.md 제거, CLAUDE.md Task Tracking/Appendix 섹션을 GitHub Issues 링크로 교체 `cc:TODO`

## MCP 서버 연결

- [ ] MCP code-sandbox 서버 연결 — `pydantic/mcp-run-python` (Docker 격리) `cc:TODO`

## Proactive Talking

> 조사 문서: [docs/todo/proactive-talking.md](docs/todo/proactive-talking.md)

- [ ] Phase 1: Idle timer 트리거 — 일정 시간 무입력 시 자동 발화 `cc:TODO`
- [ ] Phase 2: APScheduler 기반 시각 트리거 — 특정 시각 인사/알림 `cc:TODO`
- [ ] Phase 3: 외부 웹훅 트리거 — `POST /v1/proactive/trigger` `cc:TODO`

## Human in the Loop (HitL)

> 조사 문서: [docs/todo/human-in-the-loop.md](docs/todo/human-in-the-loop.md)

- [x] Phase 1: MVP — 도구 실행 전 WS 승인 요청 (`HitLRequest` / `HitLResponse` 메시지 타입 + LangGraph `interrupt()` 기반 대기/재개) `cc:DONE` — PR #36
- [ ] Phase 2: 도구 카테고리별 선택적 승인 — 위험도 분류 + `HitLMiddleware` 설정화 `cc:TODO`
- [ ] Phase 3: 인자 편집 후 재실행 — `edited_args` 지원 `cc:TODO`

## 스케줄/리마인더 (검토 필요)

- [ ] 스케줄/리마인더 시스템 — cron 기반 예약 메시지 ("3시에 알려줘") `cc:TODO`
- [ ] 감정 상태 트래킹 — 대화 감정 분석 → 캐릭터 반응 조절 `cc:TODO`
- [ ] 데스크톱 통합 트리거 — backend는 트리거/데이터 제공, 실제 OS 연동은 DH MOD 담당 `cc:TODO`

## Idea — 중간 에이전트 레이어 (추후 필요 시 추가)

> Agent 응답 시간 목표: ≤0.5초. code-sandbox 실행이 이 제약을 넘는 태스크가 반복되면
> claude code/opencode 같은 코딩 에이전트를 MCP로 연결하여 비동기 위임하는 중간 레이어 검토.
> NanoClaw delegation과 역할 경계 정리 필요 (NanoClaw = 무거운 장기 작업, 중간 에이전트 = 수 초~수십 초 자율 추론).
