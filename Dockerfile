FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /usr/local/bin/

# Create non-root user before any file operations
RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

# chown only the empty directory (instant)
RUN chown appuser:appuser /app

USER appuser

# Copy dependency files first for layer caching
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md ./

# Install only dependencies (not the project itself) for better layer caching
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser yaml_files/ ./yaml_files/

# Install the project itself now that source is present
RUN uv sync --frozen --no-dev

EXPOSE 5500

CMD ["uv", "run", "uvicorn", "src.main:get_app", "--factory", "--host", "0.0.0.0", "--port", "5500"]
