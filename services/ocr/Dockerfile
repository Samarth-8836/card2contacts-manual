# Use Bullseye (Debian 11) for maximum binary compatibility
FROM python:3.10-slim-bullseye

WORKDIR /app

# 1. Set Environment Variables to prevent Segfaults
# This restricts OpenMP/MKL to a single thread, stabilizing CPU inference
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
# Fixes potential rotation classification crashes
ENV PADDLEOCR_USE_ANGLE_CLS=true

# 2. Install system dependencies
# libgomp1 is required for the threading support
# libgl1-mesa-glx and libglib2.0-0 are for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Code
COPY main.py .

# NOTE: The model will download automatically when the container starts.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]