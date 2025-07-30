FROM ghcr.io/astral-sh/uv:debian-slim

RUN apt-get update && apt-get install -y build-essential libev4 libev-dev python3-dev

WORKDIR /project
ADD backend/pyproject.toml .
RUN uv sync
COPY backend/app/ ./app
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]