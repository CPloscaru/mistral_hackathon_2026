#!/bin/bash
# Lance backend + frontend + test onboarding Sophie en un seul script
# Usage: ./scripts/run_onboarding_test.sh

set -e
cd "$(dirname "$0")/.."

# Cleanup au exit
cleanup() {
  echo ""
  echo "Arrêt..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  exit 0
}
trap cleanup EXIT INT TERM

# Kill les process existants sur les ports
kill $(lsof -ti:8000) 2>/dev/null || true
kill $(lsof -ti:5173) 2>/dev/null || true
sleep 1

# Reset DB avant de lancer le backend
rm -f kameleon.db
echo "DB supprimée"

# Backend
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
(cd frontend && npm run dev) &
FRONTEND_PID=$!

# Attendre que les deux soient prêts
echo "Attente backend..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do sleep 1; done
echo "Backend OK"

echo "Attente frontend..."
until curl -s http://localhost:5173 > /dev/null 2>&1; do sleep 1; done
echo "Frontend OK"
echo ""

# Lancer le test
python scripts/01_first_step_onboarding.py

# Le cleanup se fait via le trap
