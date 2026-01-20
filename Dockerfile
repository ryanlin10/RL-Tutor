# Build stage for frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY frontend/ ./
RUN npm run build

# Production stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies in one layer (cache this)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Upgrade pip first (cache this)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy backend requirements and install CPU-only PyTorch (cache this layer separately)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from build stage
COPY --from=frontend-build /app/frontend/dist ./backend/static

# Create data directories
RUN mkdir -p /app/data/lecture_notes /app/data/vector_store && \
    chmod -R 755 /app/data

# Set working directory to backend
WORKDIR /app/backend

# Expose port
EXPOSE 5000

# Environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Railway handles health checks via railway.json
# No need for Docker HEALTHCHECK

# Start command - use exec form for proper signal handling
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile -"]
