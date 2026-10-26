FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends freetds-bin tdsodbc unixodbc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[test]"

COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

COPY docker/entrypoint.sh /usr/local/bin/english7-entrypoint
RUN chmod +x /usr/local/bin/english7-entrypoint

ENTRYPOINT ["english7-entrypoint"]
CMD ["uvicorn", "english7.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS runtime

FROM base AS vision
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --timeout 300 \
        torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --timeout 300 ".[vision]"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
