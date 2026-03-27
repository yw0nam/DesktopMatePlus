uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/ --unsafe-fixes --fix

# Structural architecture tests (layer boundaries, file sizes, conventions)
uv run pytest tests/structural/ -q
