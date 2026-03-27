# Backend Team Plans

> Stack: Python 3.13 / FastAPI / uv
> Test: `uv run pytest` | Lint: `sh scripts/lint.sh`

## Team Lead 운영 방식

Lead Agent → **Team Lead** (`.claude/agents/team-lead.md`) → Developer(task-worker) → Reviewer(code-reviewer) → PR

- Team Lead이 이 파일을 읽고 태스크를 등록/완료 처리함
- 구조 문제 발견 시 Lead Agent에 에스컬레이션, 코드 직접 수정 금지
- 변경 순서: backend → nanoclaw → desktop-homunculus (역순 금지)

## Active Tasks

<!-- cc:TODO / cc:WIP / cc:DONE -->

## Completed
