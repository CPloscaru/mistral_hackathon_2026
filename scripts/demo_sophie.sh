#!/bin/bash
# Demo Sophie — Playwright live dans un vrai navigateur
# Usage: ./scripts/demo_sophie.sh
#
# Prérequis: frontend sur localhost:5173 (cd frontend && npm run dev)

set -e
cd "$(dirname "$0")/.."

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

# Vérifier frontend
if ! lsof -ti:5173 > /dev/null 2>&1; then
  echo "ERREUR: Lance le frontend d'abord: cd frontend && npm run dev"
  kill $BACKEND_PID
  exit 1
fi
echo "Frontend OK"
echo ""

# Ouvrir Chrome via playwright-cli
echo "Ouverture du navigateur..."
npx playwright-cli open http://sophie.localhost:5173 --browser chrome

# Turn 1: attendre la réponse init
echo ""
echo "Turn 1 — Agent initie la conversation"
echo "  Attente de la réponse SSE..."
sleep 12
npx playwright-cli screenshot > /dev/null 2>&1
echo "  OK — Agent s'est présenté"
echo ""
echo ">>> Appuie sur Entrée pour Turn 2 (choix Andy)"
read

# Turn 2: Andy
echo "Turn 2 — Sophie choisit Andy"
npx playwright-cli fill 'textbox "Votre message"' "Andy, ça me va !"
sleep 0.5
npx playwright-cli click 'button "Envoyer"'
echo "  Attente réponse..."
sleep 15
npx playwright-cli screenshot > /dev/null 2>&1
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 3 (prénom)"
read

# Turn 3: Prénom
echo "Turn 3 — Sophie se présente"
npx playwright-cli fill 'textbox "Votre message"' "Moi c'est Sophie"
sleep 0.5
npx playwright-cli click 'button "Envoyer"'
echo "  Attente réponse..."
sleep 15
npx playwright-cli screenshot > /dev/null 2>&1
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 4 (situation)"
read

# Turn 4: Situation détaillée
echo "Turn 4 — Sophie raconte sa situation"
npx playwright-cli fill 'textbox "Votre message"' "Je suis designer graphique et web. J'ai bossé 3 ans en agence et j'ai commencé à prendre des clients en freelance à côté. J'en ai 4-5 réguliers mais j'aimerais vraiment me lancer à plein temps. Le truc c'est que tout ce qui est administratif, compta, devis, factures... j'y connais absolument rien et ça me stresse énormément."
sleep 0.5
npx playwright-cli click 'button "Envoyer"'
echo "  Attente réponse..."
sleep 20
npx playwright-cli screenshot > /dev/null 2>&1
echo "  OK"
echo ""
echo ">>> Appuie sur Entrée pour Turn 5 (besoins — final)"
read

# Turn 5: Besoins précis (devrait déclencher profiler + plan)
echo "Turn 5 — Sophie précise ses besoins (tour final)"
npx playwright-cli fill 'textbox "Votre message"' "Honnêtement les deux mais surtout la gestion. J'ai des clients qui me paient en retard, je sais pas comment faire des relances, j'ai aucun outil pour suivre mes factures et j'ai même pas de statut officiel encore. J'utilise un tableur Excel et je perds tout."
sleep 0.5
npx playwright-cli click 'button "Envoyer"'
echo "  Attente réponse (peut être plus long — profiler + recherche)..."
sleep 30
npx playwright-cli screenshot > /dev/null 2>&1
echo "  OK"

echo ""
echo "============================================================"
echo " SCÉNARIO SOPHIE TERMINÉ"
echo "============================================================"
echo ""
echo "Screenshots dans .playwright-cli/"
echo "Appuie sur Entrée pour fermer le navigateur..."
read

npx playwright-cli close
kill $BACKEND_PID 2>/dev/null || true
echo "Done."
