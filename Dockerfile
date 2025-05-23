# Builder Stage
FROM python:3.10-slim as builder

# Set working directory
WORKDIR /app

# Install necessary build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    python3-dev \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python3 -m venv /opt/venv

# Copy requirements.txt and install Python dependencies into the virtual environment
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Download the TinyLlama model
RUN mkdir -p /app/models && \
    curl -L https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q2_K.gguf -o /app/models/tinyllama-1.1b-chat-v1.0.Q2_K.gguf

# Final Stage
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the downloaded model from the builder stage
COPY --from=builder /app/models /app/models

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "frontend.app:app", "--host", "0.0.0.0", "--port", "$PORT"]
