#!/bin/bash
# Lance backend + frontend + test complet d'onboarding en un seul script
# Phase 1: conversation onboarding (collecte profil Marc)
# Phase 2: workflow séquentiel (analyse + mapping + interface)
#
# Usage: ./scripts/run_full_onboarding.sh
#
# Prérequis: avoir lancé run_onboarding_test.sh au moins une fois
#            (pour avoir un profile.json dans output/01_first_step_onboarding/)

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

# Vérifier qu'un profil existe
PROFILE_DIR=$(ls -d output/01_first_step_onboarding/*/ 2>/dev/null | sort | tail -1)
if [ -z "$PROFILE_DIR" ]; then
  echo "ERREUR: Aucun profil trouvé dans output/01_first_step_onboarding/"
  echo "Lance d'abord: ./scripts/run_onboarding_test.sh"
  exit 1
fi
echo "Profil trouvé: ${PROFILE_DIR}profile.json"

# Kill les process existants sur les ports
kill $(lsof -ti:8000) 2>/dev/null || true
kill $(lsof -ti:5173) 2>/dev/null || true
sleep 1

# Restaurer le snapshot DB s'il existe, sinon partir d'une DB fraîche
if [ -f kameleon_snapshot.db ]; then
  cp kameleon_snapshot.db kameleon.db
  echo "DB restaurée depuis snapshot (post-onboarding phase 1)"
else
  rm -f kameleon.db
  echo "Pas de snapshot — DB fraîche (le script injectera le profil)"
fi

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

# Lancer le test workflow (→ /personal-assistant avec stepper + chat + dock)
python scripts/02_second_step_plan.py

# Le cleanup se fait via le trap
