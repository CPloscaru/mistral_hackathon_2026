#!/bin/bash
# Lance backend + frontend + test complet :
#   Phase 1 : Onboarding conversationnel (Agent + Ministral 3B joue Sophie)
#   Phase 2 : Swarm plan SMART + Dashboard avec Dock
#
# Usage: ./scripts/run_full_flow_test.sh
#
# Le navigateur reste ouvert à la fin pour inspection manuelle.

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

# Reset DB
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

# Lancer le test complet (Phase 1 + Phase 2)
python scripts/run_full_flow_test.py

echo ""
echo "Test terminé. Navigateur ouvert pour inspection."
echo "Ctrl+C pour quitter."

# Garder le script vivant (le cleanup viendra du trap)
wait
