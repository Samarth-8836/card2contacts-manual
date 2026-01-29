# Backend Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend directory structure
# This creates /app/backend/ with all files inside
COPY backend /app/backend

# Expose port
EXPOSE 8000

# Run the application with proper module path
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--limit-concurrency", "1000", "--max-requests", "10000", "--max-requests-jitter", "1000", "--timeout-keep-alive", "5", "--timeout-graceful-shutdown", "30"]
