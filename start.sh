#!/bin/bash

# Start Celery worker in the background
echo "🚀 Starting Celery Worker..."
celery -A app.worker.celery_app worker --loglevel=info --concurrency=1 &

# Start FastAPI application
echo "🌐 Starting FastAPI Application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
