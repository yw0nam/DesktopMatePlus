# GitHub Issues Migration Design

**Date:** 2026-04-16
**Scope:** TODO.md + KNOWN_ISSUES.md → GitHub Issues 통합 마이그레이션

## 1. 목표

- `TODO.md`와 `docs/known_issues/KNOWN_ISSUES.md`를 GitHub Issues로 전면 이전
- 두 파일 삭제, 스크립트/문서 참조를 `gh issue list` 기반으로 전환
- Label + Milestone 체계 수립

## 2. Label 체계

### Type Labels

| Label | 설명 | 색상 |
|-------|------|------|
| `type:feature` | 신규 기능, enhancement | `#1d76db` |
| `type:bug` | 버그, 오작동 | `#d93f0b` |
| `type:refactor` | 리팩토링, chore | `#fbca04` |
| `type:docs` | 문서 추가/수정 | `#0075ca` |
| `type:tech-debt` | 기술 부채, KI 항목 | `#e4e669` |
| `type:idea` | 아이디어, 검토 필요 | `#d4c5f9` |

### Severity Labels

| Label | 설명 | 색상 |
|-------|------|------|
| `severity:low` | 미발현 또는 영향 적음 | `#c5def5` |
| `severity:medium` | 기능 제한 | `#fbca04` |
| `severity:high` | 긴급 | `#d93f0b` |

### Component Labels

| Label | 설명 | 색상 |
|-------|------|------|
| `component:agent` | Agent 서비스 | `#0e8a16` |
| `component:websocket` | WebSocket 서비스 | `#0e8a16` |
| `component:proactive` | Proactive 서비스 | `#0e8a16` |
| `component:tts` | TTS 서비스 | `#0e8a16` |
| `component:docker` | Docker/인프라 | `#0e8a16` |
| `component:mcp` | MCP 연동 | `#0e8a16` |
| `component:channel` | Channel (Slack) 서비스 | `#0e8a16` |
| `component:memory` | STM (MongoDB) / LTM (mem0) | `#0e8a16` |

### Status Labels

| Label | 설명 | 색상 |
|-------|------|------|
| `status:wontfix` | 수정하지 않기로 결정 | `#ffffff` |

## 3. Milestone 체계

| Milestone | 매핑 |
|-----------|------|
| `HitL` | HitL Phase 2, 3 |
| `MCP` | MCP code-sandbox |
| `Future Ideas` | 스케줄/리마인더, 감정 트래킹, 중간 에이전트 레이어 등 |

## 4. 이전 대상 매핑

### TODO.md → Issues (open 항목만)

| 항목 | Labels | Milestone |
|------|--------|-----------|
| MCP code-sandbox 서버 연결 | `type:feature`, `component:mcp` | MCP |
| HitL Phase 2: 카테고리별 선택적 승인 | `type:feature`, `component:agent` | HitL |
| HitL Phase 3: 인자 편집 후 재실행 | `type:feature`, `component:agent` | HitL |
| 스케줄/리마인더 시스템 | `type:idea` | Future Ideas |
| 감정 상태 트래킹 | `type:idea` | Future Ideas |
| 데스크톱 통합 트리거 | `type:idea` | Future Ideas |
| 중간 에이전트 레이어 | `type:idea` | Future Ideas |

> Proactive Phase 1~3은 이미 완료 (PR #38) — 이전하지 않음.
> HitL Phase 1은 이미 완료 (PR #36) — 이전하지 않음.
> `TODO.md + KNOWN_ISSUES.md → GitHub Issues 통합 마이그레이션` 항목은 이 마이그레이션 자체의 완료로 해소 — 이전하지 않음.

### KNOWN_ISSUES.md → Issues (open 항목)

| 항목 | Labels | Milestone |
|------|--------|-----------|
| KI-16: Docker openai_chat_agent.yml | `type:tech-debt`, `severity:low`, `component:docker` | — |
| KI-22: HitL E2E 비결정적 | `type:tech-debt`, `severity:low`, `component:agent` | HitL |
| KI-24: IdleWatcher 순차 처리 | `type:tech-debt`, `severity:low`, `component:proactive` | — |
| KI-25: ScheduleManager 순차 broadcast | `type:tech-debt`, `severity:low`, `component:proactive` | — |
| KI-26: CLAUDE.md 미들웨어 순서 stale | `type:tech-debt`, `severity:low`, `component:agent` | — |

### Won't Fix → closed 이슈 (이력 보존)

| 항목 | Labels |
|------|--------|
| KI-2: 6개 서비스 파일 200줄 초과 | `type:tech-debt`, `status:wontfix` |
| KI-3: validate_token() 항상 valid_token | `type:tech-debt`, `status:wontfix` |
| KI-7: _severity() 문자열 키워드 매칭 | `type:tech-debt`, `status:wontfix` |
| KI-11: RestrictedShellTool cwd 제한 없음 | `type:tech-debt`, `status:wontfix` |
| KI-21: scripts/run.sh YAML 경로 참조 우려 | `type:tech-debt`, `status:wontfix` |

### Resolved → 이전하지 않음

KI-18, KI-19, KI-20, KI-23은 이미 해결되어 CHANGELOG에 기록됨. 이중 기록 불필요.

## 5. 스크립트/문서 수정

| 파일 | 변경 내용 |
|------|-----------|
| `scripts/clean/garden.sh` | GP-6: `grep cc:TODO TODO.md` → `gh issue list --label type:feature --state open --json number` |
| `scripts/clean/garden.sh` | GP-9: TODO.md spec-ref 파싱 → 제거 (Issues에서는 PR 링크로 자연 추적) |
| `scripts/clean/garden.sh` | GP-10: TODO.md auto-archive → 제거 (Issues는 close로 관리) |
| `scripts/clean/check_docs.sh` | `PLANS_FILE=TODO.md` 참조 제거 |
| `.claude/commands/quality-report.md` | TODO.md Health Check → GitHub Issues 조회로 전환 |
| `CLAUDE.md` | Task Tracking 섹션 → `gh issue list`로 교체, Appendix TODO/KI 링크 제거 |
| `docs/GOLDEN_PRINCIPLES.md` | GP-6, GP-9, GP-10 규칙 텍스트를 Issues 기반으로 수정 |
| `docs/CLAUDE.md` | `known_issues/` 참조 제거 |
| `CHECKLIST.md` | TODO.md DoD 참조 → Issues 참조로 수정 |
| `docs/scripts-reference.md` | TODO.md cc:DONE spec-ref 검증 설명 → Issues 기반으로 수정 |
| `TODO.md` | 삭제 |
| `docs/known_issues/KNOWN_ISSUES.md` | 삭제 |
| `docs/known_issues/` | 디렉토리 삭제 |

> CHANGELOG.md 및 과거 quality report(`docs/reports/`)의 TODO.md/KNOWN_ISSUES.md 참조는 역사적 기록이므로 수정하지 않음.
> `docs/prds/plan/` 내 완료된 plan 문서의 "Update TODO.md" 스텝도 역사적 기록이므로 수정하지 않음.

## 6. 제약 사항

- `gh` CLI가 설치된 환경에서만 스크립트가 동작 (CI 환경 주의)
- garden.sh의 GP-6 검증은 `gh issue list` 호출 시 GitHub API rate limit 영향 가능 — 단독 개발이라 문제 없음
- garden.sh GP-6: `gh` 미설치/미인증 시 `SKIP`으로 처리 (기존 `TODO.md not found` SKIP 패턴과 동일)
