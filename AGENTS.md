# AGENTS.md — Development Flow

> **Project**: backend (DesktopMate+)
> **Language**: Python 3.13 / FastAPI
> **Orchestration**: oh-my-claudecode (OMC)

---

## Agent Setup

| Agent | subagent_type | Model | Role |
|-------|---------------|-------|------|
| **Orchestrator** | *(Claude itself)* | opus | 판단·위임·TaskCreate·PR 결정 |
| **Implementer** | `oh-my-claudecode:executor` | sonnet (complex→opus) | TDD 구현·lint·commit |
| **Reviewer** | `oh-my-claudecode:code-reviewer` | sonnet | 코드 품질·SOLID·로직 결함 |
| **Security** | `oh-my-claudecode:security-reviewer` | opus | OWASP·시크릿·취약점 검사 |
| **Debugger** | `oh-my-claudecode:tracer` / `debugger` | sonnet | 원인 추적·스택 분석 |
| **Test Engineer** | `oh-my-claudecode:test-engineer` | sonnet | TDD 전략·E2E·flaky 수정 |
| **Quality** | `.claude/agents/quality-agent.md` | sonnet | 일일 GP 검증·리포트·PR |

---

## Workflow

```
User request
     │
     ▼
[Explore agent] ──→ 큰 피처? ──→ ralplan (합의 계획)
     │                                   │
     └─────────────── TaskCreate ◄────────┘
                           │
                           ▼
                   executor (worktree 격리)
                      │  TDD: RED → GREEN → refactor
                      │  lint + tests (run_in_background)
                      │
                      ▼
              code-reviewer (별도 패스)
                      │
                      ├─→ 백엔드 변경 시: security-reviewer
                      │
                      ▼
               verifier → PR 생성 → TODO.md cc:DONE
```

---

## TDD 원칙 (필수)

모든 코드 작성은 TDD를 따른다. 예외 없음.

1. **RED**: 실패하는 테스트 먼저 작성
2. **GREEN**: 테스트가 통과하는 최소 구현
3. **REFACTOR**: 중복 제거·가독성 개선

- executor 스폰 시 항상 TDD 순서 준수
- 테스트 없는 구현 PR → code-reviewer에서 reject
- `"tdd"` 키워드로 OMC TDD 모드 자동 트리거

---

## Task Tracking

- 작업 시작: `TODO.md`에 `cc:TODO` → `cc:WIP` 마킹
- 작업 완료: DoD 전 단계 통과 후 `cc:DONE` 마킹
- 세션 내 진행 추적: `TaskCreate` / `TaskUpdate` 도구 병행 사용

---

## Model Routing

```
haiku  → 빠른 조회, 단순 질문
sonnet → 표준 구현 (executor 기본값)
opus   → 아키텍처 설계, 복잡한 디버깅, 보안 리뷰
```

---

## OMC 실행 원칙

- 독립 작업 2개 이상 → 병렬 실행 (single message, multiple tool calls)
- 빌드·테스트 → `run_in_background`
- **자가승인 금지**: 구현 컨텍스트에서 직접 승인 불가 — `code-reviewer` 별도 패스 필수
- 완료 주장 전: pending tasks 0 + tests passing + verifier 증거 수집

---

## OMC 스킬 트리거

| 키워드 | 동작 |
|--------|------|
| `"tdd"` | TDD 모드 활성화 |
| `"ralplan"` | 합의 계획 (큰 피처) |
| `"ultrathink"` | 심층 추론 |
| `"deepsearch"` | 코드베이스 탐색 |
| `"autopilot"` | 자율 실행 모드 |

---

## Task Completion Checklist (DoD)

Every task MUST pass all phases before marking `cc:DONE`.

### Full E2E check (preferred)

```bash
bash scripts/e2e.sh
```

Must output `-> e2e: PASSED`. Requires MongoDB + Qdrant running.

### Per-task unit check

```bash
scripts/check-task.sh -k <keyword>
```

Where `<keyword>` is the task identifier (e.g. `irodori`, `tts`, `slack`).

### Phases

| Phase | Command | Pass condition |
|-------|---------|----------------|
| **1 — Lint** | `sh scripts/lint.sh` | Exit 0 (ruff + black + structural tests) |
| **2 — Unit tests** | `uv run pytest -k <keyword> -v` | All collected tests pass |
| **3 — E2E** | `bash scripts/e2e.sh` | STM/LTM/WS examples exit 0 + no app ERROR logs |

### Manual steps (if e2e.sh unavailable)

```bash
# Phase 1
sh scripts/lint.sh

# Phase 2
uv run pytest -k <keyword> -v

# Phase 3 (manual)
PORT=$(( 7000 + RANDOM % 2000 ))
BACKEND_PORT=$PORT bash scripts/run.sh --bg
sleep 5
uv run python examples/test_stm.py --base-url "http://127.0.0.1:${PORT}"
uv run python examples/test_ltm.py --base-url "http://127.0.0.1:${PORT}"
uv run python examples/test_websocket.py --ws-url "ws://127.0.0.1:${PORT}/v1/chat/stream"
bash scripts/run.sh --stop
```

### Notes

- Phase 3 requires real external services (MongoDB, Qdrant). If unavailable, backend starts but `/health` returns 500 and examples will fail.
- `e2e.sh` picks a random port (7000-8999) to avoid collisions with the main app on 5500.
- LTM test auto-skips if Qdrant is not running (prints "LTM SKIPPED").
- 신규 태스크: TODO.md DoD에 `bash scripts/e2e.sh PASSED` 체크 필수.
