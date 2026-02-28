"""
Script de test automatisé du scénario d'onboarding Sophie.

Joue le scénario complet turn par turn via l'API SSE,
vérifie les réponses à chaque étape.

Usage:
    source venv/bin/activate
    python scripts/test_scenario_sophie.py

Prérequis: backend lancé sur localhost:8000
"""
import httpx
import uuid
import sys
import os
import time

# Ajouter la racine du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://sophie.localhost:8000"
SESSION_ID = str(uuid.uuid4())

# Scénario Sophie — chaque turn est (message_user, vérifications_attendues)
SCENARIO = [
    # Turn 1: Init (agent parle en premier)
    {
        "type": "init",
        "checks": ["andy", "lisa", "kameleon"],
        "description": "Turn 1 — Agent se présente et demande Andy ou Lisa",
    },
    # Turn 2: Sophie choisit Andy
    {
        "type": "message",
        "text": "Andy, ça me va !",
        "checks": ["andy"],
        "negative_checks": [],
        "description": "Turn 2 — Agent adopte le nom Andy et demande le prénom",
    },
    # Turn 3: Sophie se présente
    {
        "type": "message",
        "text": "Moi c'est Sophie",
        "checks": ["sophie"],
        "description": "Turn 3 — Agent demande son activité",
    },
    # Turn 4: Sophie raconte sa situation (turn riche)
    {
        "type": "message",
        "text": (
            "Je suis designer graphique et web. J'ai bossé 3 ans en agence "
            "et j'ai commencé à prendre des clients en freelance à côté. "
            "J'en ai 4-5 réguliers mais j'aimerais vraiment me lancer à plein temps. "
            "Le truc c'est que tout ce qui est administratif, compta, devis, factures... "
            "j'y connais absolument rien et ça me stresse énormément. "
            "Je sais même pas par où commencer."
        ),
        "checks": [],  # On vérifie juste que ça répond
        "description": "Turn 4 — Sophie décrit sa situation, agent rebondit",
    },
    # Turn 5: Sophie précise ses besoins
    {
        "type": "message",
        "text": (
            "Honnêtement les deux mais surtout la gestion. "
            "J'ai des clients qui me paient en retard, je sais pas comment faire des relances, "
            "j'ai aucun outil pour suivre mes factures et j'ai même pas de statut officiel encore. "
            "J'utilise un tableur Excel et je perds tout."
        ),
        "checks": [],
        "description": "Turn 5 — Agent produit le résumé + Swarm lance le plan + [ONBOARDING_COMPLETE]",
    },
]


def read_sse_stream(response: httpx.Response) -> dict:
    """Parse un flux SSE et retourne le texte complet + les événements."""
    full_text = ""
    events = []
    buffer = ""

    for chunk in response.iter_text():
        buffer += chunk
        while "\n\n" in buffer:
            raw_event, buffer = buffer.split("\n\n", 1)
            lines = raw_event.strip().split("\n")
            event_type = "message"
            data_parts = []

            for line in lines:
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_parts.append(line[5:].strip())

            data = "\n".join(data_parts)
            events.append({"type": event_type, "data": data})

            if event_type == "token" and data:
                full_text += data
            elif event_type == "maturity_update":
                full_text += " [MATURITY_UPDATE]"

    return {"text": full_text, "events": events}


def call_init(session_id: str) -> dict:
    """Appelle GET /chat/init pour déclencher le message d'accueil."""
    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "GET",
            f"{BASE_URL}/chat/init",
            params={"session_id": session_id},
        ) as response:
            return read_sse_stream(response)


def call_chat(session_id: str, message: str) -> dict:
    """Appelle POST /chat/stream avec un message."""
    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST",
            f"{BASE_URL}/chat/stream",
            json={"message": message, "session_id": session_id},
        ) as response:
            return read_sse_stream(response)


def check_response(result: dict, turn: dict) -> bool:
    """Vérifie que la réponse contient les éléments attendus."""
    text_lower = result["text"].lower()
    ok = True

    # Vérifications positives
    for check in turn.get("checks", []):
        if check.lower() not in text_lower:
            print(f"  FAIL: '{check}' non trouvé dans la réponse")
            ok = False

    # Vérifications négatives
    for check in turn.get("negative_checks", []):
        if check.lower() in text_lower:
            print(f"  FAIL: '{check}' trouvé dans la réponse (ne devrait pas)")
            ok = False

    # Vérifier qu'il y a du contenu
    if len(result["text"].strip()) < 10:
        print(f"  FAIL: réponse trop courte ({len(result['text'])} chars)")
        ok = False

    return ok


def run_scenario():
    """Joue le scénario complet."""
    print("=" * 60)
    print(" SCÉNARIO SOPHIE — Test d'onboarding automatisé")
    print("=" * 60)
    print(f"\nSession: {SESSION_ID}")
    print(f"Backend: {BASE_URL}\n")

    passed = 0
    failed = 0

    for i, turn in enumerate(SCENARIO):
        print(f"{'─' * 60}")
        print(f"  {turn['description']}")
        print(f"{'─' * 60}")

        try:
            if turn["type"] == "init":
                print("  > [Agent initie la conversation]")
                result = call_init(SESSION_ID)
            else:
                print(f"  > Sophie: \"{turn['text'][:80]}{'...' if len(turn['text']) > 80 else ''}\"")
                result = call_chat(SESSION_ID, turn["text"])

            # Afficher la réponse (tronquée)
            response_text = result["text"]
            display = response_text[:300] + ("..." if len(response_text) > 300 else "")
            print(f"  < Andy: \"{display}\"")
            print(f"  [{len(result['events'])} events, {len(response_text)} chars]")

            # Vérifier les événements spéciaux
            event_types = [e["type"] for e in result["events"]]
            if "maturity_update" in event_types:
                print("  [ONBOARDING_COMPLETE détecté]")

            # Vérifier
            if check_response(result, turn):
                print("  PASS")
                passed += 1
            else:
                print("  FAILED (voir erreurs ci-dessus)")
                failed += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

        print()

    # Résumé
    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f" SCÉNARIO SOPHIE: {passed}/{total} turns PASS")
    else:
        print(f" SCÉNARIO SOPHIE: {passed}/{total} turns pass, {failed} FAILED")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    # Vérifier que le backend est accessible
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        r.raise_for_status()
        print("Backend OK\n")
    except Exception as e:
        print(f"Erreur: backend non accessible sur {BASE_URL}")
        print(f"Lance d'abord: uvicorn backend.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    success = run_scenario()
    sys.exit(0 if success else 1)
