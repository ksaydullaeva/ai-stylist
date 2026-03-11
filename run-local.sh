#!/usr/bin/env bash
# Run Style Studio locally (backend + frontend). Use two terminals or run one in background.
set -e
cd "$(dirname "$0")"

echo "=== Style Studio – run locally ==="
echo ""
echo "1. Backend (Terminal 1):"
echo "   cd backend"
echo "   source venv/bin/activate   # or: python3 -m venv venv && source venv/bin/activate"
echo "   pip install -r requirements.txt   # if not already installed"
echo "   uvicorn main:app --reload --host 127.0.0.1 --port 8000"
echo ""
echo "2. Frontend (Terminal 2):"
echo "   cd web"
echo "   npm install   # if not already installed"
echo "   npm run dev"
echo ""
echo "3. Open: http://localhost:5173  (Vite proxies /api and /health to :8000)"
echo "   API docs: http://127.0.0.1:8000/docs"
echo ""
echo "Optional: create PostgreSQL DB for saving outfits:"
echo "   createdb styleai   # or: psql -U postgres -c 'CREATE DATABASE styleai;'"
echo ""

# If venv exists, start backend in background and then frontend in foreground
if [ -d "backend/venv" ]; then
  echo "Starting backend in background (backend/venv found)..."
  (cd backend && source venv/bin/activate && uvicorn main:app --reload --host 127.0.0.1 --port 8000) &
  BACKEND_PID=$!
  sleep 2
  echo "Starting frontend..."
  cd web && npm run dev
  kill $BACKEND_PID 2>/dev/null || true
else
  echo "No backend/venv found. Run the commands above in two terminals."
fi
