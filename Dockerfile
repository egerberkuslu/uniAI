FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

CMD ["python", "-m", "src.mcp.server"]
