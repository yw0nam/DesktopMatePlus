---
description: Coding standards (applies when editing source files)
paths: "src/**/*.py, tests/**/*.py"
---

# Coding Standards

## Commit Message Conventions

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat:` | New feature | `feat: add TTS streaming endpoint` |
| `fix:` | Bug fix | `fix: resolve WebSocket disconnect handling` |
| `docs:` | Documentation | `docs: update API reference` |
| `refactor:` | Refactoring | `refactor: extract agent state helpers` |
| `test:` | Tests | `test: add checkpointer integration tests` |
| `chore:` | Maintenance | `chore: bump langchain to 0.3` |

## Code Style

- Follow existing code style — match surrounding patterns
- Only modify what is necessary for the task
- No unsolicited refactoring or "improvements" to untouched code
- No excessive comments

## Python / FastAPI Specific

- Use `|` unions — never `Optional[X]` (Python 3.10+ style)
- Strict type hints on all function signatures
- `async/await` for all I/O operations
- No bare `print()` — use Loguru via `src/core/logger`
- No hardcoded config — use `settings` or YAML under `yaml_files/`
- Pydantic V2 models for all API schemas

## Pull Request

- Title: concise summary (≤ 70 chars)
- Body: describe **what** and **why**
- Include test plan
