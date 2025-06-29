# AI Agent Multi-stage Docker Build
# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/client

# Copy package files
COPY client/package*.json ./

# Install frontend dependencies
RUN npm ci --only=production

# Copy frontend source code
COPY client/ ./

# Build frontend application
RUN npm run build

# Stage 2: Backend Service
FROM python:3.11-slim AS backend

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create application user for security
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy Python requirements
COPY server/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directory structure
RUN mkdir -p server/data/{uploads,embeddings_cache,reports,sample_sales} && \
    chown -R app:app server/

# Copy backend source code
COPY server/ ./server/

# Copy initial data files
COPY docs/data/*.csv ./server/data/

# Copy frontend build output
COPY --from=frontend-builder /app/client/dist ./client/dist

# Copy project configuration files
COPY README.md ./
COPY package*.json ./

# Set file permissions
RUN chown -R app:app /app

# Switch to application user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set working directory to server
WORKDIR /app/server

# Start command for production
CMD ["python", "start.py", "--host", "0.0.0.0", "--port", "8000", "--prod", "--workers", "4"] 