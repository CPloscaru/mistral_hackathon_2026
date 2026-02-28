#!/bin/bash
# Demo Sophie — Playwright live dans un vrai navigateur
# Usage: ./scripts/demo_sophie.sh

set -e
cd "$(dirname "$0")/.."

# Helper: refresh snapshot + fill input + click send using element refs
send_message() {
  local msg="$1"
  npx playwright-cli snapshot > /dev/null 2>&1
  npx playwright-cli fill e17 "$msg"
  sleep 0.5
  npx playwright-cli snapshot > /dev/null 2>&1
  npx playwright-cli click e19
}

echo "============================================================"
echo " SCÉNARIO SOPHIE — Onboarding live (Playwright)"
echo "============================================================"

# Reset DB
rm -f kameleon_sessions.db
echo "DB supprimée"

# Restart backend
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 3
echo "Backend lancé"

if ! lsof -ti:5173 > /dev/null 2>&1; then
  echo "ERREUR: Lance le frontend d'abord: cd frontend && npm run dev"
  kill $BACKEND_PID
  exit 1
fi
echo "Frontend OK"
echo ""

echo "Ouverture du navigateur..."
npx playwright-cli open http://sophie.localhost:5173 --browser chrome --headed

echo ""
echo "Turn 1 — Agent initie la conversation"
echo "  Attente de la réponse SSE..."
sleep 15
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 2 (choix Andy)"
read

echo "Turn 2 — Sophie choisit Andy"
send_message "Andy, ça me va !"
echo "  Attente réponse..."
sleep 15
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 3 (prénom)"
read

echo "Turn 3 — Sophie se présente"
send_message "Moi c'est Sophie"
echo "  Attente réponse..."
sleep 15
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 4 (situation)"
read

echo "Turn 4 — Sophie raconte sa situation"
send_message "Je suis designer graphique et web. J'ai bossé 3 ans en agence et j'ai commencé à prendre des clients en freelance à côté. J'en ai 4-5 réguliers mais j'aimerais vraiment me lancer à plein temps. Le truc c'est que tout ce qui est administratif, compta, devis, factures... j'y connais absolument rien et ça me stresse énormément."
echo "  Attente réponse..."
sleep 20
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 5 (besoins — final)"
read

echo "Turn 5 — Sophie précise ses besoins (tour final)"
send_message "Honnêtement les deux mais surtout la gestion. J'ai des clients qui me paient en retard, je sais pas comment faire des relances, j'ai aucun outil pour suivre mes factures et j'ai même pas de statut officiel encore. J'utilise un tableur Excel et je perds tout."
echo "  Attente réponse (profiler + recherche)..."
sleep 30
echo "  OK"

echo ""
echo "============================================================"
echo " SCÉNARIO SOPHIE TERMINÉ"
echo "============================================================"
echo ""
echo "Appuie sur Entrée pour fermer..."
read

npx playwright-cli close
kill $BACKEND_PID 2>/dev/null || true
echo "Done."
