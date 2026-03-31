# Backend Project Rules

## Stack Constraints

- **Python 3.13+** — use `|` unions, no `Optional[X]`
- **Package manager**: `uv` only — never `pip install`
- **Run commands**: `uv run <cmd>`, not `python <cmd>`

## Architecture Rules

- Director role in Director-Artisan pattern — changes go backend → nanoclaw → desktop-homunculus (never reverse)
- Services live under `src/services/<name>/`; register in `src/services/__init__.py` AND `src/main.py` lifespan
- No hardcoded config values — use `settings` object or YAML under `yaml_files/`
- Logging: Loguru via `src/core/logger` — no bare `print()`

## Code Quality

- Run `sh scripts/lint.sh` before ending any task (ruff + black + structural tests)
- Structural tests in `tests/structural/` enforce layer boundaries and file size limits
- New violations fail immediately — do not add to `_KNOWN_*` sets without fixing

## Task Tracking

- Tasks tracked in `Plans.md` with `cc:TODO` / `cc:WIP` / `cc:DONE` markers
