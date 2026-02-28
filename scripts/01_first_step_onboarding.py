"""
Test automatisé — Phase 1 de l'onboarding (Agent conversationnel).

Ministral 3B joue le rôle de Sophie dans un vrai navigateur via playwright-cli.
Boucle question/réponse jusqu'à ce que l'Agent émette [READY_FOR_PLAN].
Sauvegarde le profil JSON dans output/onboarding_sophie.json.

Usage:
    source venv/bin/activate
    python scripts/01_first_step_onboarding.py

Prérequis: backend sur :8000, frontend sur :5173
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from mistralai import Mistral

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "kameleon.db"

# Dossier de sortie : output/01_first_step_onboarding/<timestamp>/
SCRIPT_NAME = Path(__file__).stem
RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
RUN_DIR = PROJECT_ROOT / "output" / SCRIPT_NAME / RUN_TIMESTAMP

# ─── Prompt de Sophie (Ministral 3B) ───────────────────────────────

SOPHIE_SYSTEM_PROMPT = """Tu es Sophie, 28 ans, designer graphique et web.
Tu parles à un assistant IA (Kameleon) qui t'aide à te lancer en freelance.

=== TA SITUATION (à révéler au fil des questions, PAS d'un coup) ===
- Tu as bossé 3 ans en agence de design (CDI)
- Tu as commencé à prendre des clients freelance à côté, t'en as 4-5 réguliers
- Tu veux quitter l'agence et te lancer à plein temps d'ici 6 mois
- Tout ce qui est administratif, compta, devis, factures : tu y connais rien et ça te stresse
- Tu gères tes trucs sur un tableur Excel et tu perds tout
- T'as des clients qui te paient en retard, tu sais pas comment relancer
- T'as même pas de statut officiel encore (pas auto-entrepreneur)

=== RÈGLES STRICTES ===
- Tu RÉPONDS UNIQUEMENT à la question posée. Rien d'autre.
- Si on te demande de choisir entre Andy et Lisa → réponds juste "Andy !" ou "Je préfère Andy !"
- Si on te demande ton prénom → "Moi c'est Sophie !" et c'est tout
- Tu ne donnes JAMAIS de conseils, tu ne proposes JAMAIS d'options, tu n'es PAS un assistant
- Tu es une UTILISATRICE, pas une experte. Tu ne sais rien sur l'admin/les statuts
- Réponses COURTES : 1 à 3 phrases max
- Tu ne résumes PAS ta situation d'un coup — seulement quand on te pose la question
- Pas de listes à puces, pas de mise en forme, juste du texte naturel
"""

# ─── Playwright-CLI helpers ────────────────────────────────────────


def pw(cmd: str) -> str:
    """Exécute une commande playwright-cli et retourne le stdout."""
    result = subprocess.run(
        f"npx playwright-cli {cmd}",
        shell=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return result.stdout.strip()


def pw_eval(js: str) -> str:
    """Exécute du JS via playwright-cli eval et retourne le résultat parsé."""
    # playwright-cli eval wraps code as: page.evaluate('() => (<code>)')
    # So we must pass a simple expression, not an IIFE
    result = subprocess.run(
        ["npx", "playwright-cli", "eval", js],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    raw = result.stdout.strip()
    # Format: "### Result\n<value>\n### Ran Playwright code..."
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "### Result" and i + 1 < len(lines):
            return lines[i + 1].strip()
    return ""


def get_last_assistant_message() -> str:
    """Lit le textContent du dernier message assistant dans le DOM."""
    # pw_eval wraps as () => (<expr>), so use comma operator for multi-step
    return pw_eval(
        "[...document.querySelectorAll('.message-bubble--assistant')].pop()?.innerText || ''"
    ).strip()


def wait_for_response(prev_msg: str = "", timeout: int = 60) -> str:
    """
    Poll le DOM : attend qu'un nouveau message assistant apparaisse
    (différent de prev_msg) et que le typing-indicator disparaisse.
    """
    start = time.time()
    time.sleep(2)

    while time.time() - start < timeout:
        still_typing = pw_eval(
            "!!document.querySelector('.typing-indicator-row')"
        )
        if still_typing == "false":
            text = get_last_assistant_message()
            # Vérifier que c'est un NOUVEAU message (pas l'ancien)
            if text and text != prev_msg:
                return text
        time.sleep(1)

    # Fallback : lire quand même ce qui est dans le DOM
    text = get_last_assistant_message()
    if text and text != prev_msg:
        return text
    return "[TIMEOUT]"


def send_message_browser(text: str):
    """Tape un message dans le chat via JS (indépendant des refs playwright)."""
    safe_text = text.replace("'", "\\'").replace("\n", "\\n")
    # Remplir le textarea via React-compatible value setter
    pw_eval(
        f"(()=>{{const ta=document.querySelector('textarea[aria-label=\"Votre message\"]');"
        f"const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;"
        f"set.call(ta,'{safe_text}');"
        f"ta.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"ta.dispatchEvent(new Event('change',{{bubbles:true}}))}})()"
    )
    time.sleep(0.3)
    # Cliquer le bouton Envoyer
    pw_eval(
        "document.querySelector('button[aria-label=\"Envoyer\"]').click()"
    )


# ─── Détection ready_for_plan via SQLite ───────────────────────────


def check_db_for_profile() -> dict | None:
    """
    Lit la dernière session creator dans SQLite.
    Retourne le onboarding_data si non vide, sinon None.
    """
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT onboarding_data FROM sessions "
            "WHERE persona = 'creator' ORDER BY rowid DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            data = json.loads(row[0])
            if isinstance(data, dict) and data.get("prenom"):
                return data
    except Exception:
        pass
    return None


# ─── Sophie (Ministral 3B) ────────────────────────────────────────


def sophie_responds(client: Mistral, conversation: list[dict], agent_message: str) -> str:
    """Ministral 3B génère la réponse de Sophie."""
    conversation.append({"role": "user", "content": agent_message})

    response = client.chat.complete(
        model="ministral-3b-2512",
        messages=[{"role": "system", "content": SOPHIE_SYSTEM_PROMPT}] + conversation,
        max_tokens=300,
        temperature=0.7,
    )

    sophie_reply = response.choices[0].message.content.strip()
    conversation.append({"role": "assistant", "content": sophie_reply})
    return sophie_reply


# ─── Main ──────────────────────────────────────────────────────────


def run():
    print("=" * 60)
    print(" ONBOARDING SOPHIE — Phase 1 (Agent conversationnel)")
    print(" Sophie jouée par Ministral 3B | Affichage navigateur")
    print("=" * 60)

    # Init Mistral client
    api_key = os.getenv("MISTRAL_API")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("MISTRAL_API")
    if not api_key:
        print("ERREUR: MISTRAL_API non trouvée dans .env")
        sys.exit(1)
    mistral_client = Mistral(api_key=api_key)

    sophie_conversation: list[dict] = []
    # Log de la conversation complète (agent + sophie)
    conversation_log: list[dict] = []

    # Créer le dossier de run
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {RUN_DIR}\n")

    # Ouvrir le navigateur
    print("\nOuverture du navigateur...")
    pw("open http://sophie.localhost:5173 --browser chrome --headed")

    # Turn 0 : Init — l'agent salue
    print(f"\n{'─' * 60}")
    print(f"  Turn 0 — Agent initie la conversation")
    print(f"{'─' * 60}")
    agent_msg = wait_for_response(timeout=30)
    print(f"  Agent: {agent_msg[:300]}{'...' if len(agent_msg) > 300 else ''}")
    conversation_log.append({"turn": 0, "role": "agent", "text": agent_msg})

    # Boucle conversationnelle
    turn = 0
    profile = None
    while True:
        turn += 1

        # Sophie (3B) génère sa réponse
        sophie_reply = sophie_responds(mistral_client, sophie_conversation, agent_msg)

        print(f"\n{'─' * 60}")
        print(f"  Turn {turn}")
        print(f"{'─' * 60}")
        print(f"  Sophie: {sophie_reply}")
        conversation_log.append({"turn": turn, "role": "sophie", "text": sophie_reply})

        # Envoyer dans le navigateur
        send_message_browser(sophie_reply)

        # Attendre la réponse de l'agent
        agent_msg = wait_for_response(timeout=60)
        print(f"  Agent:  {agent_msg[:400]}{'...' if len(agent_msg) > 400 else ''}")
        conversation_log.append({"turn": turn, "role": "agent", "text": agent_msg})

        # Vérifier si le profil a été sauvegardé en DB (= ready_for_plan)
        profile = check_db_for_profile()
        if profile:
            print(f"\n{'=' * 60}")
            print(" [READY_FOR_PLAN] détecté !")
            print(f"{'=' * 60}")
            break

        if turn >= 15:
            print("\n TIMEOUT: 15 turns sans [READY_FOR_PLAN]")
            break

    # ─── Sauvegarde des résultats ──────────────────────────────────
    # Profil JSON
    if profile:
        profile_path = RUN_DIR / "profile.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(f"\n Profil: {profile_path}")
        print(f" {json.dumps(profile, ensure_ascii=False, indent=2)}")

    # Conversation complète
    conv_path = RUN_DIR / "conversation.json"
    with open(conv_path, "w", encoding="utf-8") as f:
        json.dump(conversation_log, f, ensure_ascii=False, indent=2)
    print(f" Conversation: {conv_path} ({turn} turns)")

    print(f"\n Run: {RUN_DIR}")
    print("Done. Navigateur ouvert pour inspection.")


if __name__ == "__main__":
    run()
