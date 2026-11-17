# syntax=docker/dockerfile:1
FROM python:3.11-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY app ./app

FROM python:3.11-slim
RUN useradd --uid 1000 --create-home yiji \
    && mkdir /data /backups \
    && chown yiji:yiji /data /backups
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    YIJI_HOST=0.0.0.0 \
    YIJI_PORT=8100 \
    YIJI_RELOAD=false \
    YIJI_DATA_DIR=/data \
    YIJI_BACKUP_DIR=/backups \
    NICEGUI_STORAGE_PATH=/data/.nicegui
USER yiji
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"YIJI_PORT\"]}/api/health', timeout=4)"]
CMD ["python", "-m", "app"]
