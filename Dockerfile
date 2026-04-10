# Multi-stage build for combined frontend + backend deployment

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
ARG VITE_GITHUB_REPO_URL=""
ENV VITE_GITHUB_REPO_URL=$VITE_GITHUB_REPO_URL
RUN npm run build

# Stage 2: Build backend
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app ./app

# Copy frontend build
COPY --from=frontend-build /frontend/dist ./static

# Create startup script that serves both
RUN pip install aiofiles

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Railway etc. set PORT; default 8000 for local Docker
CMD sh -c "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
