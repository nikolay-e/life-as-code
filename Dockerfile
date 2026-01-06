# Life-as-Code Health Analytics Platform - Multi-Stage Build

# --- Builder Stage ---
FROM python:3.11-slim AS builder

# Build arguments for versioning
ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml .
COPY src/ src/

# Install Python dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# --- Runtime Stage ---
FROM python:3.11-slim

# Build arguments for versioning (redeclared for this stage)
ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

# Labels for container metadata
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.authors="Nikolay Eremeev" \
      org.opencontainers.image.url="https://github.com/nikolay-e/life-as-code" \
      org.opencontainers.image.source="https://github.com/nikolay-e/life-as-code" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.title="Life-as-Code Backend" \
      org.opencontainers.image.description="Multi-user health analytics platform"

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code and migrations
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .
COPY docker-entrypoint.sh .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Create non-root user for security with numeric UID
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser && \
    chown -R appuser:appuser /app && \
    chmod +x docker-entrypoint.sh

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${VERSION} \
    BUILD_DATE=${BUILD_DATE} \
    VCS_REF=${VCS_REF}

# Switch to non-root user
USER 1000

# Expose port for dashboard
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=3)" || exit 1

# Default command
CMD ["./docker-entrypoint.sh"]
