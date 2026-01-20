# Build stage for frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Production stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from build stage
COPY --from=frontend-build /app/frontend/dist ./backend/static

# Create data directories
RUN mkdir -p /app/data/lecture_notes /app/data/vector_store

# Set working directory to backend
WORKDIR /app/backend

# Expose port (Railway uses PORT env var)
EXPOSE ${PORT:-5000}

# Environment variable for port
ENV PORT=5000

# Start command - uses shell form to expand $PORT
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
