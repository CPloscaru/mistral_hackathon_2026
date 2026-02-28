#!/bin/bash
# Demo Sophie — Reset + API calls uniquement
# Ouvre ton navigateur sur http://sophie.localhost:5173/ et lance ce script.
# Le script reset la DB et appelle les mêmes endpoints que le frontend.
# Tu vois les réponses dans le terminal ET en live dans ton navigateur
# (à condition de rafraîchir la page après le reset).
#
# Usage:
#   ./scripts/demo_sophie.sh

set -e
cd "$(dirname "$0")/.."
source venv/bin/activate

echo "============================================================"
echo " SCÉNARIO SOPHIE — Onboarding (API-only)"
echo "============================================================"

# Reset DB pour session fraîche
rm -f kameleon_sessions.db
echo "DB supprimée. Redémarre le backend..."

# Restart backend
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 3

# Vérifier backend
curl -sf http://sophie.localhost:8000/health > /dev/null || { echo "Backend KO"; kill $BACKEND_PID; exit 1; }
echo "Backend OK"
echo ""
echo ">>> Rafraîchis ton navigateur sur http://sophie.localhost:5173/"
echo ">>> Puis appuie sur Entrée pour lancer le scénario"
read

# Session ID fixe pour ce test
SID="demo-sophie-$(date +%s)"
echo "Session: $SID"
echo ""

# Turn 1: Init
echo "────────────────────────────────────────────────────────"
echo "  Turn 1 — Agent initie la conversation"
echo "────────────────────────────────────────────────────────"
echo ""
curl -sN "http://sophie.localhost:8000/chat/init?session_id=$SID" | while IFS= read -r line; do
  if [[ "$line" == data:* ]]; then
    data="${line#data: }"
    if [[ "$data" != *'"done"'* && "$data" != *'"error"'* ]]; then
      printf "%s" "$data"
    fi
  fi
done
echo ""
echo ""
echo ">>> Appuie sur Entrée pour Turn 2"
read

# Turn 2: Choisir Andy
echo "────────────────────────────────────────────────────────"
echo "  Turn 2 — Sophie: \"Andy, ça me va !\""
echo "────────────────────────────────────────────────────────"
echo ""
curl -sN -X POST "http://sophie.localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Andy, ça me va !\", \"session_id\": \"$SID\"}" | while IFS= read -r line; do
  if [[ "$line" == data:* ]]; then
    data="${line#data: }"
    if [[ "$data" != *'"done"'* && "$data" != *'"error"'* ]]; then
      printf "%s" "$data"
    fi
  fi
done
echo ""
echo ""
echo ">>> Appuie sur Entrée pour Turn 3"
read

# Turn 3: Se présenter
echo "────────────────────────────────────────────────────────"
echo "  Turn 3 — Sophie: \"Moi c'est Sophie\""
echo "────────────────────────────────────────────────────────"
echo ""
curl -sN -X POST "http://sophie.localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Moi c'est Sophie\", \"session_id\": \"$SID\"}" | while IFS= read -r line; do
  if [[ "$line" == data:* ]]; then
    data="${line#data: }"
    if [[ "$data" != *'"done"'* && "$data" != *'"error"'* ]]; then
      printf "%s" "$data"
    fi
  fi
done
echo ""
echo ""
echo ">>> Appuie sur Entrée pour Turn 4"
read

# Turn 4: Situation
echo "────────────────────────────────────────────────────────"
echo "  Turn 4 — Sophie raconte sa situation"
echo "────────────────────────────────────────────────────────"
echo ""
MSG4="Je suis designer graphique et web. J'ai bossé 3 ans en agence et j'ai commencé à prendre des clients en freelance à côté. J'en ai 4-5 réguliers mais j'aimerais vraiment me lancer à plein temps. Le truc c'est que tout ce qui est administratif, compta, devis, factures... j'y connais absolument rien et ça me stresse énormément."
curl -sN -X POST "http://sophie.localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MSG4\", \"session_id\": \"$SID\"}" | while IFS= read -r line; do
  if [[ "$line" == data:* ]]; then
    data="${line#data: }"
    if [[ "$data" != *'"done"'* && "$data" != *'"error"'* ]]; then
      printf "%s" "$data"
    fi
  fi
done
echo ""
echo ""
echo ">>> Appuie sur Entrée pour Turn 5 (final)"
read

# Turn 5: Besoins
echo "────────────────────────────────────────────────────────"
echo "  Turn 5 — Sophie précise ses besoins"
echo "────────────────────────────────────────────────────────"
echo ""
MSG5="Honnêtement les deux mais surtout la gestion. J'ai des clients qui me paient en retard, je sais pas comment faire des relances, j'ai aucun outil pour suivre mes factures et j'ai même pas de statut officiel encore. J'utilise un tableur Excel et je perds tout."
curl -sN -X POST "http://sophie.localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MSG5\", \"session_id\": \"$SID\"}" | while IFS= read -r line; do
  if [[ "$line" == data:* ]]; then
    data="${line#data: }"
    if [[ "$data" != *'"done"'* && "$data" != *'"error"'* && "$data" != *'maturity'* ]]; then
      printf "%s" "$data"
    fi
    if [[ "$data" == *'maturity'* ]]; then
      echo ""
      echo ""
      echo "  >>> [ONBOARDING_COMPLETE] détecté !"
    fi
  fi
done
echo ""
echo ""

echo "============================================================"
echo " SCÉNARIO SOPHIE TERMINÉ"
echo "============================================================"

# Cleanup
kill $BACKEND_PID 2>/dev/null || true
