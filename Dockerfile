# Production Dockerfile for Nova Credit AI
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Train model during build if not present
RUN python src/train_model.py

# Expose ports for Streamlit (8501) and Backend REST API (8085)
EXPOSE 8501 8085

# Default command launches Streamlit Dashboard
CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
