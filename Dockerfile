# Multi-stage Dockerfile supporting development and production targets for the MCP server.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src
WORKDIR /app

# Development image with tooling and hot-reload
FROM base AS development
RUN python -m venv ${VENV_PATH}
COPY pyproject.toml README.md ./
COPY src ./src
RUN ${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel
RUN ${VENV_PATH}/bin/pip install -e '.[dev,test,lint]'
EXPOSE 8000
CMD ["uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Builder image installs runtime dependencies into an isolated virtual environment
FROM base AS builder
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv ${VENV_PATH}
COPY pyproject.toml README.md ./
COPY src ./src
RUN ${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel
RUN ${VENV_PATH}/bin/pip install .

# Production image keeps only the runtime environment and application sources
FROM base AS production
COPY --from=builder ${VENV_PATH} ${VENV_PATH}
COPY src/mcp_server ./src/mcp_server
EXPOSE 8000
CMD ["uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
