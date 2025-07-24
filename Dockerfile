FROM ghcr.io/astral-sh/uv:debian-slim
WORKDIR /project
ADD backend/pyproject.toml .
RUN uv sync
COPY backend/app/ ./app
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]