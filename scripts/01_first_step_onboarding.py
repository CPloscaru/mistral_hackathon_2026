"""
Test automatise - Phase 1 de l'onboarding (Agent conversationnel).

Ministral 3B joue le role de Marc dans un vrai navigateur via playwright-cli.
Boucle question/reponse jusqu'a ce que l'Agent emette [READY_FOR_PLAN].
Sauvegarde le profil JSON dans output/01_first_step_onboarding/<timestamp>/profile.json.

Mode browser-UI : les messages sont envoyes via le textarea + clic Envoyer
pour un streaming natif token par token dans le navigateur.

Usage:
    source venv/bin/activate
    python scripts/01_first_step_onboarding.py

Prerequis: backend sur :8000, frontend sur :5173
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

# --- Prompt de Marc (Ministral 3B) ----------------------------------------

MARC_SYSTEM_PROMPT = """Tu es Marc, 28 ans, designer graphique et web.
Tu parles a un assistant IA (Kameleon) qui t'aide a te lancer en freelance.

=== TA SITUATION (a reveler au fil des questions, PAS d'un coup) ===
- Tu as bosse 3 ans en agence de design (CDI)
- Tu as commence a prendre des clients freelance a cote, t'en as 4-5 reguliers
- Tu veux quitter l'agence et te lancer a plein temps d'ici 6 mois
- Tout ce qui est administratif, compta, devis, factures : tu y connais rien et ca te stresse
- Tu geres tes trucs sur un tableur Excel et tu perds tout
- T'as des clients qui te paient en retard, tu sais pas comment relancer
- T'as meme pas de statut officiel encore (pas auto-entrepreneur)

=== REGLES STRICTES ===
- Tu REPONDS UNIQUEMENT a la question posee. Rien d'autre.
- Si on te demande de choisir entre Andy et Lisa -> reponds juste "Andy !" ou "Je prefere Andy !"
- Si on te demande ton prenom -> "Moi c'est Marc !" et c'est tout
- Tu ne donnes JAMAIS de conseils, tu ne proposes JAMAIS d'options, tu n'es PAS un assistant
- Tu es un UTILISATEUR, pas un expert. Tu ne sais rien sur l'admin/les statuts
- Reponses COURTES : 1 a 3 phrases max
- Tu ne resumes PAS ta situation d'un coup -- seulement quand on te pose la question
- Pas de listes a puces, pas de mise en forme, juste du texte naturel
"""

# --- Playwright-CLI helpers ------------------------------------------------


def pw(cmd: str) -> str:
    """Execute une commande playwright-cli et retourne le stdout."""
    result = subprocess.run(
        f"npx playwright-cli {cmd}",
        shell=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return result.stdout.strip()


def pw_eval(js: str) -> str:
    """Execute du JS via playwright-cli eval et retourne le resultat parse."""
    result = subprocess.run(
        ["npx", "playwright-cli", "eval", js],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    raw = result.stdout.strip()
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "### Result" and i + 1 < len(lines):
            return lines[i + 1].strip()
    return ""


# --- DB helpers -----------------------------------------------------------


def load_active_session_from_db() -> str | None:
    """Retourne le session_id de la dernière session en DB."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT session_id FROM sessions ORDER BY rowid DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def load_messages_from_db(session_id: str) -> list[dict]:
    """Charge les messages d'une session depuis SQLite."""
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in rows]
    except Exception:
        return []


def check_db_for_profile() -> dict | None:
    """
    Lit la derniere session dans SQLite.
    Retourne le onboarding_data si non vide, sinon None.
    """
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT onboarding_data FROM sessions "
            "WHERE persona = 'default' ORDER BY rowid DESC LIMIT 1"
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


# --- Browser UI helpers ---------------------------------------------------


def wait_for_greeting_dom(timeout: int = 60) -> str:
    """Poll le DOM pour le premier message assistant (greeting).
    Attend que le typing indicator disparaisse et qu'un message assistant existe."""
    start = time.time()
    while time.time() - start < timeout:
        typing = pw_eval("!!document.querySelector('.typing-indicator-row')")
        if typing == "false":
            msg = pw_eval(
                "[...document.querySelectorAll('.message-bubble--assistant')].pop()?.innerText || ''"
            )
            if msg:
                return msg
        time.sleep(1)
    return "[TIMEOUT]"


def send_message_browser(text: str):
    """Remplit le textarea et clique Envoyer via le DOM."""
    safe = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    pw_eval(
        f"(()=>{{const ta=document.querySelector('textarea[aria-label=\"Votre message\"]');"
        f"const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;"
        f"set.call(ta,'{safe}');"
        f"ta.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"ta.dispatchEvent(new Event('change',{{bubbles:true}}));"
        f"setTimeout(()=>document.querySelector('button[aria-label=\"Envoyer\"]').click(),100)}})()"
    )


def wait_for_response_db(session_id: str, prev_count: int, timeout: int = 120) -> str:
    """Poll DB pour un nouveau message assistant (count > prev_count)."""
    start = time.time()
    while time.time() - start < timeout:
        messages = load_messages_from_db(session_id)
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        if len(assistant_msgs) > prev_count:
            return assistant_msgs[-1]["content"]
        time.sleep(1)
    return "[TIMEOUT]"


# --- Marc (Ministral 3B) --------------------------------------------------


def marc_responds(client: Mistral, conversation: list[dict], agent_message: str) -> str:
    """Ministral 3B genere la reponse de Marc."""
    conversation.append({"role": "user", "content": agent_message})

    response = client.chat.complete(
        model="ministral-3b-2512",
        messages=[{"role": "system", "content": MARC_SYSTEM_PROMPT}] + conversation,
        max_tokens=300,
        temperature=0.7,
    )

    marc_reply = response.choices[0].message.content.strip()
    conversation.append({"role": "assistant", "content": marc_reply})
    return marc_reply


# --- Main ------------------------------------------------------------------


def run():
    print("=" * 60)
    print(" ONBOARDING MARC -- Phase 1 (Agent conversationnel)")
    print(" Marc joue par Ministral 3B | Mode browser-UI")
    print("=" * 60)

    # Init Mistral client
    api_key = os.getenv("MISTRAL_API")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("MISTRAL_API")
    if not api_key:
        print("ERREUR: MISTRAL_API non trouvee dans .env")
        sys.exit(1)
    mistral_client = Mistral(api_key=api_key)

    marc_conversation: list[dict] = []
    conversation_log: list[dict] = []

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {RUN_DIR}\n")

    # Ouvrir le navigateur sur la WelcomePage
    print("\nOuverture du navigateur...")
    pw("open http://localhost:5173 --browser chrome --headed")

    # Attendre que l'utilisateur clique sur "Commencer"
    print("En attente du clic sur 'Commencer'...")
    while True:
        on_chat = pw_eval("window.location.pathname")
        if "/chat" in on_chat:
            break
        time.sleep(1)
    print("Page /chat chargee.")

    # Lire le session_id depuis la DB (session active)
    # La session est créée par /chat/init — attendre qu'elle apparaisse
    print("Attente de la session en DB...")
    session_id = None
    for _ in range(30):
        session_id = load_active_session_from_db()
        if session_id:
            break
        time.sleep(1)
    if not session_id:
        print("ERREUR: aucune session active trouvée en DB après 30s")
        sys.exit(1)
    print(f"Session ID: {session_id}")

    # Turn 0 : Init -- attendre le greeting via DOM polling
    print(f"\n{'--' * 30}")
    print(f"  Turn 0 -- Agent initie la conversation")
    print(f"{'--' * 30}")
    agent_msg = wait_for_greeting_dom(timeout=60)
    print(f"  Agent: {agent_msg[:300]}{'...' if len(agent_msg) > 300 else ''}")
    conversation_log.append({"turn": 0, "role": "agent", "text": agent_msg})

    # Compter les messages assistant en DB pour le polling
    messages_db = load_messages_from_db(session_id)
    assistant_count = len([m for m in messages_db if m["role"] == "assistant"])

    # Boucle conversationnelle
    turn = 0
    profile = None
    while True:
        turn += 1

        # Marc (3B) genere sa reponse
        marc_reply = marc_responds(mistral_client, marc_conversation, agent_msg)

        print(f"\n{'--' * 30}")
        print(f"  Turn {turn}")
        print(f"{'--' * 30}")
        print(f"  Marc: {marc_reply}")
        conversation_log.append({"turn": turn, "role": "marc", "text": marc_reply})

        # Envoyer via le browser UI (streaming natif)
        send_message_browser(marc_reply)

        # Attendre la reponse de l'agent via DB polling
        agent_msg = wait_for_response_db(session_id, assistant_count, timeout=120)
        assistant_count += 1
        print(f"  Agent:  {agent_msg[:400]}{'...' if len(agent_msg) > 400 else ''}")
        conversation_log.append({"turn": turn, "role": "agent", "text": agent_msg})

        # Verifier ready_for_plan via DB (profil sauvegarde)
        profile = check_db_for_profile()
        if profile:
            print(f"\n{'=' * 60}")
            print(" [READY_FOR_PLAN] detecte !")
            print(f"{'=' * 60}")
            break

        if turn >= 15:
            print("\n TIMEOUT: 15 turns sans [READY_FOR_PLAN]")
            break

    # Attendre le clic sur "OK, allons-y !"
    if profile:
        print("En attente du clic sur 'OK, allons-y !'...")
        while True:
            path = pw_eval("window.location.pathname")
            if "/personal-assistant" in path:
                break
            time.sleep(1)
        print("Navigation vers /personal-assistant detectee.")

    # --- Sauvegarde des resultats ------------------------------------------
    if profile:
        profile_path = RUN_DIR / "profile.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(f"\n Profil: {profile_path}")
        print(f" {json.dumps(profile, ensure_ascii=False, indent=2)}")

    conv_path = RUN_DIR / "conversation.json"
    with open(conv_path, "w", encoding="utf-8") as f:
        json.dump(conversation_log, f, ensure_ascii=False, indent=2)
    print(f" Conversation: {conv_path} ({turn} turns)")

    print(f"\n Run: {RUN_DIR}")
    print("Done. Navigateur ouvert pour inspection.")


if __name__ == "__main__":
    run()
