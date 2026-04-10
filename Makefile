.PHONY: lint test e2e run fmt clean

# Lint: black + ruff + structural tests
lint:
	sh scripts/lint.sh

# Unit tests only (excludes e2e and slow markers)
test:
	uv run pytest tests/ -m "not e2e and not slow" -q

# End-to-end test suite (requires MongoDB + Qdrant + external services)
e2e:
	bash scripts/e2e.sh

# Format code with black and ruff
fmt:
	uv run black src/ tests/
	uv run ruff check --fix src/ tests/

# Start the FastAPI dev server (foreground)
run:
	bash scripts/run.sh

# Remove Python cache and test artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -f .run.pid .run.logdir
