---
name: team-context
description: Backend Team context. Auto-loaded for all backend tasks. Defines stack, test commands, and conventions.
---

# Backend Team Context

## Stack
- Python 3.13 + uv (never pip)
- FastAPI + Pydantic
- Loguru (never bare print)
- MongoDB (STM), Mem0 (LTM)

## Commands
```bash
uv run pytest              # 전체 테스트
uv run pytest tests/foo.py # 특정 파일
sh scripts/lint.sh         # ruff lint + format check
```

## Conventions
- Config: `yaml_files/` + Pydantic settings (하드코딩 금지)
- Services: `src/services/{name}/` → `__init__.py` + `main.py` lifespan 등록
- Routes: `src/api/routes/__init__.py`에 라우터 추가, 항상 `response_model`/`status_code`/`responses` 포함
- Type hints: strict, `|` union style (Python 3.10+)

## 태스크 완료 후 메모리 업데이트

태스크가 끝날 때마다 다음을 점검한다:

- 새로운 패턴이나 설계 결정을 발견했는가? → `backend/CLAUDE.md` 업데이트
- 다음에 혼동될 수 있는 내용인가? → `docs/faq/` 에 추가
- 판단 기준: "다음 Subagent가 이 맥락 없이 같은 실수를 할 수 있는가?"

## Plans
See: `Plans.md` in this directory
