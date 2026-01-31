#!/bin/bash
echo "Starting FastAPI Backend..."
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
