#!/bin/bash
# Development entrypoint — runs backend + frontend dev server
set -e

# Start backend in background
cd /app
uvicorn alejandria.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend dev server in background
cd /app/frontend
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

# Wait for both
wait $BACKEND_PID $FRONTEND_PID
