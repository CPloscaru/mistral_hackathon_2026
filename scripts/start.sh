#!/usr/bin/env bash
# Lance le backend, le frontend, et ouvre Chrome sur l'app.
#
# Usage:
#   ./scripts/start.sh          → mode normal (ouvre Chrome)
#   ./scripts/start.sh auto     → mode auto (LLM joue le user, enchaîne phase 1 + 2)
#   ./scripts/start.sh resume   → relance les serveurs sans reset DB, ouvre Chrome
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-normal}"

cleanup() {
  echo ""
  echo "Arrêt des services..."
  kill $PID_BACK $PID_FRONT 2>/dev/null || true
  exit 0
}
trap cleanup EXIT INT TERM

# Kill les process existants sur les ports
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# En mode auto, reset la DB pour repartir de zéro
if [ "$MODE" = "auto" ]; then
  rm -f "$ROOT/kameleon.db"
  echo "Mode auto — DB supprimée"
fi

# Backend
cd "$ROOT"
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
PID_BACK=$!

# Frontend
(cd "$ROOT/frontend" && npm run dev -- --port 5173 --strictPort) &
PID_FRONT=$!

# Attendre que les deux soient prêts
echo "Attente backend..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do sleep 1; done
echo "Backend OK  → http://localhost:8000"

echo "Attente frontend..."
until curl -s http://localhost:5173 > /dev/null 2>&1; do sleep 1; done
echo "Frontend OK → http://localhost:5173"
echo ""

if [ "$MODE" = "auto" ]; then
  echo "═══════════════════════════════════════════════════════"
  echo " MODE AUTO — LLM pilote l'onboarding de bout en bout"
  echo "═══════════════════════════════════════════════════════"
  echo ""

  # Phase 1 : onboarding conversationnel (Marc joue par Ministral 3B)
  echo "Phase 1 -- Onboarding conversationnel..."
  python scripts/01_first_step_onboarding.py

  echo ""
  echo "Phase 2 -- Workflow sequentiel (analyse + interface)..."
  python scripts/02_second_step_plan.py

  echo ""
  echo "═══════════════════════════════════════════════════════"
  echo " AUTO terminé — navigateur déjà sur /personal-assistant"
  echo "═══════════════════════════════════════════════════════"

  # Le navigateur est déjà ouvert sur /personal-assistant par le script 02
  # Pas besoin d'ouvrir un nouvel onglet
  echo "Ctrl+C pour tout arrêter."
  wait

elif [ "$MODE" = "resume" ]; then
  echo "═══════════════════════════════════════════════════════"
  echo " MODE RESUME — DB conservée, reprise en l'état"
  echo "═══════════════════════════════════════════════════════"
  echo ""
  open -na "Google Chrome" --args --new-window "http://localhost:5173/personal-assistant"
  echo "Ctrl+C pour tout arrêter."
  wait

else
  # Mode normal : ouvrir Chrome
  open -a "Google Chrome" http://localhost:5173
  echo "Ctrl+C pour tout arrêter."
  wait
fi
