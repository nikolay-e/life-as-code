# Life-as-Code Health Analytics Platform - Multi-Stage Build

# --- Deps Stage (cached on pyproject.toml only) ---
FROM python:3.13-slim AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
RUN mkdir -p src && touch src/__init__.py

RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

# --- ML Builder Stage (branches BEFORE src/ copy — PyTorch cached on pyproject.toml) ---
FROM deps AS ml-builder
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install torch --index-url https://download.pytorch.org/whl/cu121
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install '.[ml]'

# --- Bot Builder Stage (branches BEFORE src/ copy) ---
FROM deps AS bot-builder
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install '.[agent,bot]'

# --- Web Builder Stage (agent extra for chat) ---
FROM deps AS web-builder
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install '.[agent]'

# --- Builder Stage (adds source code — busts only on src/ changes) ---
FROM web-builder AS builder

COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps .

# --- Runtime Base ---
FROM python:3.13-slim AS runtime-base

WORKDIR /app

COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

RUN mkdir -p /app/data /app/logs /app/models && \
    groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser && \
    chown -R appuser:appuser /app

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# --- Web Runtime Stage ---
FROM runtime-base AS web

ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

COPY --from=builder /opt/venv /opt/venv
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

ENV PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${VERSION} \
    BUILD_DATE=${BUILD_DATE} \
    VCS_REF=${VCS_REF}

LABEL org.opencontainers.image.title="Life-as-Code Backend" \
      org.opencontainers.image.version="${VERSION}"

USER 1000
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=3)" || exit 1

CMD ["./docker-entrypoint.sh"]

# --- ML Runtime Stage ---
FROM runtime-base AS ml

ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

COPY --from=ml-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${VERSION} \
    BUILD_DATE=${BUILD_DATE} \
    VCS_REF=${VCS_REF}

LABEL org.opencontainers.image.title="Life-as-Code ML Pipeline"

USER 1000

CMD ["python", "-m", "ml.run", "--user-id", "1", "--train"]

# --- Bot Runtime Stage ---
FROM runtime-base AS bot

ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

COPY --from=bot-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${VERSION} \
    BUILD_DATE=${BUILD_DATE} \
    VCS_REF=${VCS_REF}

LABEL org.opencontainers.image.title="Life-as-Code Telegram Bot"

USER 1000

CMD ["python", "-m", "bot"]
