FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install only dependencies (not the project itself) for better layer caching
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY src/ ./src/
COPY yaml_files/ ./yaml_files/

# Install the project itself now that source is present
RUN uv sync --frozen --no-dev

# Create non-root user and transfer ownership
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5500

CMD ["uv", "run", "uvicorn", "src.main:get_app", "--factory", "--host", "0.0.0.0", "--port", "5500"]
