uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/ --unsafe-fixes --fix
