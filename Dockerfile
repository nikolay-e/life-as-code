# Life-as-Code Health Analytics Platform - Multi-Stage Build

# --- Builder Stage (base) ---
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copy ONLY dependency spec (cached unless pyproject.toml changes)
COPY pyproject.toml .

# 2. Create minimal package structure to satisfy pip
RUN mkdir -p src && touch src/__init__.py

# 3. Install all dependencies (this layer is cached on pyproject.toml hash)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# 4. Copy actual source code (only this layer busts on code changes)
COPY src/ src/

# 5. Reinstall project only, deps already cached (fast)
RUN pip install --no-cache-dir --no-deps .

# --- ML Builder Stage ---
FROM builder AS ml-builder
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121
RUN pip install --no-cache-dir '.[ml]'

# --- Bot Builder Stage ---
FROM builder AS bot-builder
RUN pip install --no-cache-dir '.[agent,bot]'

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
