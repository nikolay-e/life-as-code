# Life-as-Code Health Analytics Platform
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install all dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port for dashboard
EXPOSE 8050

# Create a startup script that runs data pulls and starts dashboard
RUN chmod +x docker-entrypoint.sh

# Default command
CMD ["./docker-entrypoint.sh"]
