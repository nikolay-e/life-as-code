# Life-as-Code Health Analytics Platform
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first for dependency installation
COPY pyproject.toml .

# Install dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Change ownership of app directory to appuser
RUN chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expose port for dashboard
EXPOSE 8080

# Create a startup script that runs data pulls and starts dashboard
RUN chmod +x docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Default command
CMD ["./docker-entrypoint.sh"]
