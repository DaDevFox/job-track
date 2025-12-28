#!/bin/bash
# Start the FastAPI backend server

echo "Starting Job Track API server..."
cd "$(dirname "$0")"
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
