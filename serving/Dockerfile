FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY serving/requirements-serving.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-serving.txt sentencepiece

# Copy service code
COPY service.py .
COPY export_tokens.py .

# Standardize running on unique port 2202
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "2202"]
