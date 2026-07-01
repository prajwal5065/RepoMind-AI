FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer-cache friendly)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code only
COPY backend/ .

# Create data directories with correct ownership
RUN mkdir -p data/uploads data/faiss_index data/faiss_indexes

# Create a non-root user and switch to it (principle of least privilege)
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run uvicorn — bind to all interfaces so Docker port mapping works.
# In production, place a reverse proxy (nginx/caddy) in front.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
