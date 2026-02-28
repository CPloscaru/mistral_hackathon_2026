"""
Test automatisé — Phase 2 de l'onboarding (Swarm one-shot plan SMART).

Lit le profil JSON du dernier run 01_first_step_onboarding, snapshot la DB,
injecte les données d'onboarding dans une nouvelle session, déclenche le Swarm
via le navigateur et sauvegarde le plan produit.

Usage:
    source venv/bin/activate
    python scripts/02_second_step_plan.py

    # Juste restaurer le snapshot sans relancer:
    python scripts/02_second_step_plan.py --restore-only

Prérequis: backend sur :8000, frontend sur :5173
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "kameleon.db"
SNAPSHOT_PATH = PROJECT_ROOT / "kameleon_snapshot.db"

# Dossier de sortie : output/02_second_step_plan/<timestamp>/
SCRIPT_NAME = Path(__file__).stem
RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
RUN_DIR = PROJECT_ROOT / "output" / SCRIPT_NAME / RUN_TIMESTAMP


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
    """Lit le textContent du dernier message assistant dans le DOM."""
    return pw_eval(
        "[...document.querySelectorAll('.message-bubble--assistant')].pop()?.textContent || ''"
    ).strip()


def wait_for_response(prev_msg: str = "", timeout: int = 180) -> str:
    """
    Poll le DOM : attend qu'un nouveau message assistant apparaisse
    (différent de prev_msg) et que le streaming soit terminé.

    Vérifie .message-bubble--streaming (pas .typing-indicator-row,
    qui disparaît dès les premiers tokens).
    """
    start = time.time()
    time.sleep(3)

    while time.time() - start < timeout:
        # Vérifie si un message est encore en cours de streaming
        still_streaming = pw_eval(
            "!!document.querySelector('.message-bubble--streaming')"
        )
        if still_streaming == "false":
            text = get_last_assistant_message()
            if text and text != prev_msg:
                return text
        time.sleep(2)

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


# ─── DB helpers ────────────────────────────────────────────────────


def find_latest_profile() -> dict | None:
    """
    Cherche le profil JSON le plus récent dans output/01_first_step_onboarding/.
    Retourne le dict si trouvé, sinon None.
    """
    base = PROJECT_ROOT / "output" / "01_first_step_onboarding"
    if not base.exists():
        return None

    # Trier les sous-dossiers par timestamp (nom du dossier = timestamp)
    subdirs = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
    for subdir in subdirs:
        profile_path = subdir / "profile.json"
        if profile_path.exists():
            with open(profile_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("prenom"):
                print(f"  Profil trouvé: {profile_path}")
                return data
    return None


def snapshot_db():
    """Copie kameleon.db → kameleon_snapshot.db."""
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, SNAPSHOT_PATH)
        print(f"  Snapshot: {SNAPSHOT_PATH}")
    else:
        print("  AVERTISSEMENT: kameleon.db introuvable, pas de snapshot")


def restore_db():
    """Restaure kameleon.db depuis kameleon_snapshot.db."""
    if SNAPSHOT_PATH.exists():
        shutil.copy2(SNAPSHOT_PATH, DB_PATH)
        print(f"  DB restaurée depuis: {SNAPSHOT_PATH}")
    else:
        print("  AVERTISSEMENT: kameleon_snapshot.db introuvable, pas de restauration")


def get_latest_creator_session_id() -> str | None:
    """
    Lit la dernière session creator dans SQLite.
    Retourne le session_id ou None.
    """
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT session_id FROM sessions "
            "WHERE persona = 'creator' ORDER BY rowid DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"  ERREUR DB: {e}")
        return None


def inject_onboarding_data(session_id: str, profile: dict):
    """
    Injecte le profil JSON dans la session via l'API backend.
    Cela met à jour à la fois la mémoire et SQLite.
    """
    import urllib.request

    payload = json.dumps(
        {"session_id": session_id, "profile": profile},
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        "http://sophie.localhost:8000/chat/inject-onboarding",
        data=payload,
        headers={"Content-Type": "application/json", "Host": "sophie.localhost:8000"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"  onboarding_data injecté via API pour session: {session_id}")
            else:
                print(f"  ERREUR API: {result}")
    except Exception as e:
        print(f"  ERREUR injection API: {e}")
        # Fallback : injection directe SQLite
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute(
            "UPDATE sessions SET onboarding_data = ? WHERE session_id = ?",
            (json.dumps(profile, ensure_ascii=False), session_id),
        )
        conn.commit()
        conn.close()
        print(f"  Fallback: onboarding_data injecté via SQLite pour session: {session_id}")


def check_maturity_level(session_id: str) -> int | None:
    """Lit le maturity_level de la session dans SQLite."""
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


def get_session_state(session_id: str) -> dict:
    """Lit l'état complet de la session depuis SQLite."""
    if not DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT session_id, persona, maturity_level, onboarding_data, assistant_name "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "session_id": row[0],
                "persona": row[1],
                "maturity_level": row[2],
                "onboarding_data": json.loads(row[3]) if row[3] else {},
                "assistant_name": row[4],
            }
    except Exception:
        pass
    return {}


# ─── Main ──────────────────────────────────────────────────────────


def run():
    print("=" * 60)
    print(" ONBOARDING SOPHIE — Phase 2 (Swarm one-shot plan SMART)")
    print(" Crée session en DB → ouvre navigateur → Swarm produit plan")
    print("=" * 60)

    # 1. Trouver le profil du dernier run 01
    print("\n1. Recherche du profil d'onboarding...")
    profile = find_latest_profile()
    if not profile:
        print("ERREUR: Aucun profil trouvé dans output/01_first_step_onboarding/")
        print("Lancez d'abord: python scripts/01_first_step_onboarding.py")
        sys.exit(1)
    print(f"  Prénom: {profile.get('prenom')}, Activité: {profile.get('activite')}")

    # 2. Snapshot de la DB
    print("\n2. Snapshot de la base de données...")
    snapshot_db()

    # 3. Créer le dossier de sortie
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n3. Run dir: {RUN_DIR}")

    # 4. Créer la session en DB avec le profil d'onboarding pré-injecté
    import uuid
    session_id = str(uuid.uuid4())
    print(f"\n4. Pré-création de la session en DB...")
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute(
        "INSERT OR REPLACE INTO sessions "
        "(session_id, persona, assistant_name, maturity_level, onboarding_data) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, "creator", "Andy", 1, json.dumps(profile, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    print(f"  session_id: {session_id}")
    print(f"  onboarding_data pré-injecté ({len(json.dumps(profile))} chars)")

    # 5. Ouvrir le navigateur avec ?session_id=XXX
    #    Le frontend lit le query param → utilise notre session_id
    #    Le backend charge la session depuis SQLite → voit onboarding_data → swap au Swarm
    print("\n5. Ouverture du navigateur...")
    pw(f"open http://sophie.localhost:5173?session_id={session_id} --browser chrome --headed")

    # 6. Attendre la réponse du Swarm (plan SMART — peut être long)
    print("\n6. Attente du plan SMART (Swarm — jusqu'à 180s)...")
    plan_text = wait_for_response(prev_msg="", timeout=180)

    if plan_text == "[TIMEOUT]":
        print("  ERREUR: Timeout en attente du plan Swarm")
        plan_text = get_last_assistant_message() or "[TIMEOUT]"

    print(f"\n  Plan reçu ({len(plan_text)} chars):")
    print(f"  {plan_text[:500]}{'...' if len(plan_text) > 500 else ''}")

    # 7. Vérifier [ONBOARDING_COMPLETE] (ne doit PAS apparaître dans le DOM)
    print("\n7. Vérification: [ONBOARDING_COMPLETE] absent du DOM...")
    sentinel_visible = "[ONBOARDING_COMPLETE]" in plan_text
    if sentinel_visible:
        print("  ERREUR: [ONBOARDING_COMPLETE] visible dans le DOM !")
    else:
        print("  OK: sentinel absent du texte visible")

    # 8. Vérifier le maturity_level en DB
    print("\n8. Vérification du maturity_level...")
    maturity = check_maturity_level(session_id)
    if maturity == 2:
        print(f"  OK: maturity_level = {maturity} (transition 1→2 réussie)")
    else:
        print(f"  AVERTISSEMENT: maturity_level = {maturity} (attendu: 2)")

    # 9. Sauvegarder les résultats
    print("\n9. Sauvegarde des résultats...")

    plan_path = RUN_DIR / "plan.txt"
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(plan_text)
    print(f"  Plan: {plan_path}")

    profile_path = RUN_DIR / "profile_input.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"  Profil input: {profile_path}")

    session_state = get_session_state(session_id)
    state_path = RUN_DIR / "session_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(session_state, f, ensure_ascii=False, indent=2)
    print(f"  État session: {state_path}")

    # 10. Restaurer le snapshot DB (pour pouvoir relancer)
    print("\n10. Restauration du snapshot DB...")
    restore_db()

    print(f"\n{'=' * 60}")
    print(f" Run terminé: {RUN_DIR}")
    print(f" maturity_level final: {maturity}")
    print(f" [ONBOARDING_COMPLETE] dans DOM: {sentinel_visible}")
    print("=" * 60)
    print("Navigateur ouvert pour inspection.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 2 onboarding — Swarm one-shot plan SMART"
    )
    parser.add_argument(
        "--restore-only",
        action="store_true",
        help="Restaure uniquement le snapshot DB sans relancer le Swarm",
    )
    args = parser.parse_args()

    if args.restore_only:
        print("Restauration du snapshot DB...")
        restore_db()
        print("Done.")
    else:
        run()
