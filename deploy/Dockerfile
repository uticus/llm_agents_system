# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cached layer) using only the lockfiles.
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev || uv sync --no-install-project --no-dev

# Then the source.
COPY src ./src
COPY configs ./configs
RUN uv sync --no-dev || true

# Default: run the test/import smoke check. Replace with the real entrypoint
# (e.g. an agent server) as the project grows.
CMD ["uv", "run", "python", "-c", "import llm_agents; print('llm_agents ready')"]
