#!/bin/bash
# Demo Sophie — Ouvre un vrai navigateur et joue le scénario d'onboarding
# Usage: ./scripts/demo_sophie.sh

set -e
cd "$(dirname "$0")/.."

echo "=== RESET ==="
rm -f kameleon_sessions.db
echo "DB supprimée"

# Restart backend
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 3
echo "Backend lancé (PID $BACKEND_PID)"

# Vérifier que le frontend tourne
if ! lsof -ti:5173 > /dev/null 2>&1; then
  echo "Lance le frontend d'abord: cd frontend && npm run dev"
  kill $BACKEND_PID
  exit 1
fi

echo ""
echo "=== SCÉNARIO SOPHIE — Onboarding ==="
echo ""

# Ouvre le navigateur (headed)
npx playwright-cli open http://sophie.localhost:5173 --browser chrome

echo "Turn 1: Agent initie... (attente 12s pour la réponse SSE)"
sleep 12
npx playwright-cli screenshot

echo ""
echo "Turn 2: Sophie choisit Andy"
npx playwright-cli fill "textbox \"Votre message\"" "Andy, ça me va !"
sleep 1
npx playwright-cli click "button \"Envoyer\""
echo "  Attente réponse... (15s)"
sleep 15
npx playwright-cli screenshot

echo ""
echo "Turn 3: Sophie se présente"
npx playwright-cli fill "textbox \"Votre message\"" "Moi c'est Sophie"
sleep 1
npx playwright-cli click "button \"Envoyer\""
echo "  Attente réponse... (15s)"
sleep 15
npx playwright-cli screenshot

echo ""
echo "Turn 4: Sophie raconte sa situation"
npx playwright-cli fill "textbox \"Votre message\"" "Je suis designer graphique et web. J'ai bossé 3 ans en agence et j'ai commencé à prendre des clients en freelance à côté. J'en ai 4-5 réguliers mais j'aimerais vraiment me lancer à plein temps. Le truc c'est que tout ce qui est administratif, compta, devis, factures... j'y connais absolument rien et ça me stresse énormément."
sleep 1
npx playwright-cli click "button \"Envoyer\""
echo "  Attente réponse... (20s)"
sleep 20
npx playwright-cli screenshot

echo ""
echo "Turn 5: Sophie précise ses besoins"
npx playwright-cli fill "textbox \"Votre message\"" "Honnêtement les deux mais surtout la gestion. J'ai des clients qui me paient en retard, je sais pas comment faire des relances, j'ai aucun outil pour suivre mes factures et j'ai même pas de statut officiel encore. J'utilise un tableur Excel et je perds tout."
sleep 1
npx playwright-cli click "button \"Envoyer\""
echo "  Attente réponse... (30s — le profiler + recherche vont tourner)"
sleep 30
npx playwright-cli screenshot

echo ""
echo "=== SCÉNARIO TERMINÉ ==="
echo "Screenshots dans .playwright-cli/"
echo "Appuie sur Entrée pour fermer le navigateur..."
read

npx playwright-cli close
kill $BACKEND_PID 2>/dev/null || true
