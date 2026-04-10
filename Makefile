.PHONY: lint test e2e run fmt clean

# Lint: black + ruff + structural tests
lint:
	sh scripts/lint.sh

# Unit tests only (excludes slow/e2e markers)
test:
	uv run pytest tests/ -m "not slow" -q

# End-to-end test suite (requires MongoDB + Qdrant + external services)
e2e:
	bash scripts/e2e.sh

# Start the FastAPI dev server (foreground)
run:
	bash scripts/run.sh

# Format source code with black
fmt:
	uv run black src/ tests/

# Remove Python cache and test artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -f .run.pid .run.logdir
