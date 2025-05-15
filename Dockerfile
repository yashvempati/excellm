# Use Python slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/app/model_cache
ENV HF_HOME=/app/model_cache

# Set up working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create model cache directory
RUN mkdir -p /app/model_cache

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Pre-download models
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download('TheBloke/Mistral-7B-v0.1-GGUF', 'mistral-7b-v0.1.Q4_K_M.gguf')"

# Copy application code
COPY . .

# Run the application
CMD uvicorn frontend.app:app --host 0.0.0.0 --port $PORT 
