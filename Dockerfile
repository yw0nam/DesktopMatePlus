FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev extras in production image)
RUN uv sync --frozen --no-dev

# Copy application source
COPY src/ ./src/
COPY yaml_files/ ./yaml_files/

EXPOSE 5500

CMD ["uv", "run", "uvicorn", "src.main:get_app", "--factory", "--host", "0.0.0.0", "--port", "5500"]
