"""
Test automatisé — Flow complet Onboarding → Swarm → Dashboard.

Phase 1 : Agent conversationnel (Ministral 3B joue Sophie)
Phase 2 : Navigation auto vers /personal-assistant, Swarm plan SMART
Phase 3 : Vérification dashboard (objectif SMART + Dock + tools)

Usage:
    source venv/bin/activate
    python scripts/run_full_flow_test.py

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

# Dossier de sortie
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
    result = subprocess.run(
        f"npx playwright-cli {cmd}",
        shell=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return result.stdout.strip()


def pw_eval(js: str) -> str:
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


def get_last_assistant_message() -> str:
    return pw_eval(
        "[...document.querySelectorAll('.message-bubble--assistant')].pop()?.innerText || ''"
    ).strip()


def wait_for_response(prev_msg: str = "", timeout: int = 60) -> str:
    start = time.time()
    time.sleep(2)
    while time.time() - start < timeout:
        still_typing = pw_eval(
            "!!document.querySelector('.typing-indicator-row')"
        )
        if still_typing == "false":
            text = get_last_assistant_message()
            if text and text != prev_msg:
                return text
        time.sleep(1)
    text = get_last_assistant_message()
    if text and text != prev_msg:
        return text
    return "[TIMEOUT]"


def send_message_browser(text: str):
    safe_text = text.replace("'", "\\'").replace("\n", "\\n")
    pw_eval(
        f"(()=>{{const ta=document.querySelector('textarea[aria-label=\"Votre message\"]');"
        f"const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;"
        f"set.call(ta,'{safe_text}');"
        f"ta.dispatchEvent(new Event('input',{{bubbles:true}}));"
        f"ta.dispatchEvent(new Event('change',{{bubbles:true}}))}})()"
    )
    time.sleep(0.3)
    pw_eval(
        "document.querySelector('button[aria-label=\"Envoyer\"]').click()"
    )


def check_db_for_profile() -> dict | None:
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


def sophie_responds(client: Mistral, conversation: list[dict], agent_message: str) -> str:
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


# ─── Phase 2 : attente plan + dashboard ────────────────────────────


def wait_for_page_navigation(target_path: str, timeout: int = 30) -> bool:
    """Attend que le navigateur navigue vers target_path."""
    start = time.time()
    while time.time() - start < timeout:
        current_url = pw_eval("window.location.pathname")
        if target_path in current_url:
            return True
        time.sleep(1)
    return False


def wait_for_plan_display(timeout: int = 180) -> str:
    """Attend que l'objectif SMART s'affiche (après spinner + typewriter)."""
    start = time.time()
    time.sleep(5)
    while time.time() - start < timeout:
        has_spinner = pw_eval("!!document.querySelector('.spinner-overlay')")
        if has_spinner == "true":
            time.sleep(2)
            continue
        objectif = pw_eval(
            "document.querySelector('.smart-display__objectif')?.textContent || ''"
        ).strip()
        if objectif and len(objectif) > 10:
            return objectif
        time.sleep(2)
    return "[TIMEOUT]"


def wait_for_dock(timeout: int = 60) -> bool:
    """Attend que le dock apparaisse avec les 3 icônes visibles."""
    start = time.time()
    while time.time() - start < timeout:
        count = pw_eval(
            "document.querySelectorAll('.dock__item--visible').length"
        )
        if count == "3":
            return True
        time.sleep(1)
    return False


def get_session_id_from_url() -> str:
    """Récupère le session_id depuis l'URL courante."""
    return pw_eval(
        "new URLSearchParams(window.location.search).get('session_id') || ''"
    ).strip()


def check_maturity_level(session_id: str) -> int | None:
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT maturity_level FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def check_tools_data(session_id: str) -> dict:
    """Vérifie que les tools_data ont été persistées en DB."""
    result = {"admin_checklist": 0, "calendar_events": 0}
    if not DB_PATH.exists():
        return result
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM admin_checklist WHERE session_id = ?",
            (session_id,),
        )
        result["admin_checklist"] = cursor.fetchone()[0]
        cursor = conn.execute(
            "SELECT COUNT(*) FROM calendar_events WHERE session_id = ?",
            (session_id,),
        )
        result["calendar_events"] = cursor.fetchone()[0]
        conn.close()
    except Exception:
        pass
    return result


# ─── Main ──────────────────────────────────────────────────────────


def run():
    print("=" * 70)
    print("  FULL FLOW TEST — Onboarding → Swarm → Dashboard")
    print("  Sophie jouée par Ministral 3B | Navigateur Chrome")
    print("=" * 70)

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
    conversation_log: list[dict] = []

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {RUN_DIR}\n")

    # ════════════════════════════════════════════════════════════════
    # PHASE 1 : Onboarding conversationnel
    # ════════════════════════════════════════════════════════════════
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  PHASE 1 — Onboarding conversationnel                  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    print("Ouverture du navigateur...")
    pw("open http://sophie.localhost:5173 --browser chrome --headed")

    # Turn 0 : l'agent salue
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
        sophie_reply = sophie_responds(mistral_client, sophie_conversation, agent_msg)

        print(f"\n{'─' * 60}")
        print(f"  Turn {turn}")
        print(f"{'─' * 60}")
        print(f"  Sophie: {sophie_reply}")
        conversation_log.append({"turn": turn, "role": "sophie", "text": sophie_reply})

        send_message_browser(sophie_reply)
        agent_msg = wait_for_response(timeout=60)
        print(f"  Agent:  {agent_msg[:400]}{'...' if len(agent_msg) > 400 else ''}")
        conversation_log.append({"turn": turn, "role": "agent", "text": agent_msg})

        profile = check_db_for_profile()
        if profile:
            print(f"\n  >>> [READY_FOR_PLAN] détecté ! Profil: {profile.get('prenom')}")
            break
        if turn >= 15:
            print("\n  TIMEOUT: 15 turns sans [READY_FOR_PLAN]")
            break

    # Sauvegarder résultats phase 1
    if profile:
        with open(RUN_DIR / "profile.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    with open(RUN_DIR / "conversation.json", "w", encoding="utf-8") as f:
        json.dump(conversation_log, f, ensure_ascii=False, indent=2)

    if not profile:
        print("\nERREUR: Pas de profil récupéré. Arrêt du test.")
        sys.exit(1)

    # ════════════════════════════════════════════════════════════════
    # PHASE 2 : Navigation → /personal-assistant + Swarm
    # ════════════════════════════════════════════════════════════════
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  PHASE 2 — Swarm plan SMART + Dashboard                ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    print("Attente de la navigation vers /personal-assistant...")
    navigated = wait_for_page_navigation("/personal-assistant", timeout=30)
    if navigated:
        print("  Navigation OK")
    else:
        print("  Navigation pas encore faite, attente...")
        time.sleep(5)
        navigated = wait_for_page_navigation("/personal-assistant", timeout=15)
        if not navigated:
            print("  ERREUR: Pas de navigation vers /personal-assistant")
            sys.exit(1)

    session_id = get_session_id_from_url()
    print(f"  session_id: {session_id}")

    # Attente du spinner + plan SMART
    print("\nAttente de l'objectif SMART (spinner → typewriter)...")
    objectif_text = wait_for_plan_display(timeout=180)

    if objectif_text == "[TIMEOUT]":
        print("  ERREUR: Timeout en attente de l'objectif SMART")
    else:
        print(f"\n  Objectif ({len(objectif_text)} chars):")
        print(f"  \"{objectif_text[:250]}{'...' if len(objectif_text) > 250 else ''}\"")

    # ════════════════════════════════════════════════════════════════
    # PHASE 3 : Vérification Dashboard
    # ════════════════════════════════════════════════════════════════
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  PHASE 3 — Vérification Dashboard                      ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # Dock visible ?
    print("Attente du Dock (3 icônes)...")
    dock_ok = wait_for_dock(timeout=60)
    print(f"  Dock: {'OK (3 icônes visibles)' if dock_ok else 'ERREUR'}")

    # Maturity level
    maturity = check_maturity_level(session_id)
    print(f"  Maturity level: {maturity} (attendu: 2)")

    # Tools data en DB
    tools = check_tools_data(session_id)
    print(f"  Admin checklist: {tools['admin_checklist']} items en DB")
    print(f"  Calendar events: {tools['calendar_events']} events en DB")

    # Sauvegarder résultats
    with open(RUN_DIR / "plan.txt", "w", encoding="utf-8") as f:
        f.write(objectif_text)

    results = {
        "session_id": session_id,
        "objectif_length": len(objectif_text),
        "dock_visible": dock_ok,
        "maturity_level": maturity,
        "tools_data": tools,
        "turns_onboarding": turn,
    }
    with open(RUN_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ─── Résumé ────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("  RÉSUMÉ")
    print(f"{'═' * 70}")
    print(f"  Onboarding:     {turn} turns → profil OK ({profile.get('prenom')})")
    print(f"  Objectif SMART: {'OK' if objectif_text != '[TIMEOUT]' else 'TIMEOUT'} ({len(objectif_text)} chars)")
    print(f"  Dock:           {'OK' if dock_ok else 'ERREUR'}")
    print(f"  Maturity:       {maturity}")
    print(f"  Admin items:    {tools['admin_checklist']}")
    print(f"  Calendar items: {tools['calendar_events']}")
    print(f"  Run dir:        {RUN_DIR}")
    print(f"{'═' * 70}")
    print("\nNavigateur ouvert pour inspection manuelle.")


if __name__ == "__main__":
    run()
