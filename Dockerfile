# Use Python slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set up working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Create model directory
RUN mkdir -p /app/models

# Download the TinyLlama model
RUN curl -L https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf -o /app/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

# Copy application code
COPY . .

# Run the application
CMD uvicorn frontend.app:app --host 0.0.0.0 --port $PORT 
