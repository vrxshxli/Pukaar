#!/usr/bin/env bash
# One-command start for macOS and Linux.
# Usage: ./start.sh            (rules mode)
#        LLM_MODE=ollama ./start.sh
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

if [ ! -d backend/.venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend packages..."
  (cd frontend && npm install)
fi
echo "Building the frontend..."
(cd frontend && npm run build)

echo ""
echo "Pukaar is starting on http://localhost:$PORT (LLM_MODE=${LLM_MODE:-rules})"
echo "Landing page:       http://localhost:$PORT/"
echo "Officer dashboard:  http://localhost:$PORT/control"
echo "Citizen chat:       http://localhost:$PORT/chat"
echo ""
cd backend
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
