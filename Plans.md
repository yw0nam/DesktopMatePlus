# Backend Plans.md

> Stack: Python 3.13 / FastAPI / uv
> Test: `uv run pytest` | Lint: `sh scripts/lint.sh`

Created: 2026-03-27

---

## Phase 2: Observability — Agent Run Environment

> spec: `../docs/superpowers/specs/2026-03-28-backend-agent-run-env-design.md`

| Task | Content | DoD | Depends | Status |
|------|------|-----|---------|--------|
| OBS-1 | `scripts/log_query.py` — Loguru 로그 파싱 + --level/--last/--since/--summary | `uv run python scripts/log_query.py --summary` 정상 출력 | - | cc:DONE |
| OBS-2 | `scripts/logs.sh` — log_query.py thin wrapper + 로그 파일 자동 감지 | `scripts/logs.sh --level ERROR --summary` 동작 | OBS-1 | cc:DONE |
| OBS-3 | `scripts/run.sh` — 포트 해시, LOG_DIR 격리, 외부 서비스 체크, --bg/--stop/--port | `--bg` 기동 후 `--port` 일관 출력 + `logs/worktree-{name}/` 생성 + `--stop` 정상 종료 | - | cc:DONE |
| OBS-4 | `scripts/verify.sh` — health + examples + 로그 클린 체크, exit 0/1 | `verify.sh` exit 0 (전체 PASS) | OBS-2, OBS-3 | cc:DONE |

## Phase 3: 메트릭 관측 가능성 (Metrics Observability)

> spec: TBD (Phase 5 설계 후 작성)

| Task | Content | DoD | Depends | Status |
|------|------|-----|---------|--------|
| MET-1 | FastAPI `/metrics` 엔드포인트 — request latency, error rate, active connections | `GET /metrics` → Prometheus 포맷 응답 | - | removed |
| MET-2 | `scripts/metrics.sh` — worktree별 메트릭 조회 + 임계값 초과 알림 | `scripts/metrics.sh --latency p99` 정상 출력 | MET-1 | removed |

## Phase 1: Active

| Task | Content | DoD | Depends | Status |
|------|------|-----|---------|--------|

## Completed

| Task | Content | DoD | Depends | Status |
|------|------|-----|---------|--------|
