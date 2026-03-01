"""
Test automatisé — Phase 2 de l'onboarding (workflow séquentiel).

Lit le profil JSON du dernier run 01_first_step_onboarding, snapshot la DB,
injecte les données d'onboarding dans une nouvelle session, ouvre
/personal-assistant et attend le stepper + l'interface finale.

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


def wait_for_interface(timeout: int = 240) -> bool:
    """
    Poll le DOM : attend que le stepper finisse et que l'interface (dock + chat) s'affiche.
    Retourne True si l'interface est prête, False en cas de timeout.
    """
    start = time.time()
    time.sleep(3)  # Laisser le temps au stepper de démarrer

    while time.time() - start < timeout:
        # Vérifier si le stepper est encore visible
        has_stepper = pw_eval(
            "!!document.querySelector('.stepper-overlay')"
        )
        if has_stepper == "true":
            # Log l'étape en cours
            current_step = pw_eval(
                "document.querySelector('.stepper__step--in_progress .stepper__step-label')?.textContent || ''"
            )
            done_steps = pw_eval(
                "document.querySelectorAll('.stepper__step--done').length"
            )
            print(f"  Stepper: {done_steps}/3 terminées — en cours: {current_step}")
            time.sleep(3)
            continue

        # Vérifier si le dock est visible (= interface prête)
        has_dock = pw_eval(
            "!!document.querySelector('.dock')"
        )
        if has_dock == "true":
            return True

        # Vérifier si on est en phase ready (chat visible)
        has_chat = pw_eval(
            "!!document.querySelector('.personal-assistant__chat')"
        )
        if has_chat == "true":
            return True

        time.sleep(2)

    return False


def get_welcome_message() -> str:
    """Récupère le premier message assistant dans le chat."""
    return pw_eval(
        "document.querySelector('.personal-assistant__msg--assistant')?.textContent || ''"
    ).strip()


def get_dock_tools() -> list[str]:
    """Récupère la liste des outils dans le dock."""
    raw = pw_eval(
        "JSON.stringify([...document.querySelectorAll('.dock__item')].map(el => el.querySelector('.dock__label')?.textContent || ''))"
    )
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


# ─── DB helpers ────────────────────────────────────────────────────


def find_latest_profile() -> dict | None:
    """
    Cherche le profil JSON le plus récent dans output/01_first_step_onboarding/.
    """
    base = PROJECT_ROOT / "output" / "01_first_step_onboarding"
    if not base.exists():
        return None

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


def get_objectifs_from_db() -> list[dict]:
    """Lit les objectifs persistés en DB."""
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT id, rang, objectif, urgence, impact, tool_type, raison, statut "
            "FROM objectifs ORDER BY rang"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "rang": r[1], "objectif": r[2], "urgence": r[3],
                "impact": r[4], "tool_type": r[5], "raison": r[6], "statut": r[7],
            }
            for r in rows
        ]
    except Exception:
        return []


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


def get_session_state(session_id: str) -> dict:
    """Lit l'état complet de la session depuis SQLite."""
    if not DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.execute(
            "SELECT session_id, persona, maturity_level, onboarding_data, assistant_name, active_components "
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
                "active_components": json.loads(row[5]) if row[5] else [],
            }
    except Exception:
        pass
    return {}


# ─── Main ──────────────────────────────────────────────────────────


def run():
    print("=" * 60)
    print(" ONBOARDING MARC — Phase 2 (Workflow séquentiel)")
    print(" → /personal-assistant avec stepper + chat + dock")
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

    # 4. Vérifier si le navigateur est déjà sur /personal-assistant
    #    (enchaînement automatique depuis script 01)
    current_path = pw_eval("window.location.pathname")
    if "/personal-assistant" in current_path:
        # Browser déjà sur la bonne page — lire session depuis DB
        session_id = load_active_session_from_db()
        if not session_id:
            print("ERREUR: aucune session active trouvée en DB")
            sys.exit(1)
        print(f"\n4. Navigateur déjà sur /personal-assistant — réutilisation de la session")
        print(f"  session_id: {session_id}")
    else:
        # Mode standalone — créer une nouvelle session et naviguer
        import uuid
        session_id = str(uuid.uuid4())
        print(f"\n4. Pré-création de la session en DB...")
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute(
            "INSERT OR REPLACE INTO sessions "
            "(session_id, persona, assistant_name, maturity_level, onboarding_data) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, "default", None, 1, json.dumps(profile, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        print(f"  session_id: {session_id}")
        print(f"  onboarding_data pré-injecté ({len(json.dumps(profile))} chars)")

        # Ouvrir le navigateur directement sur /personal-assistant
        print("\n5. Ouverture du navigateur sur /personal-assistant...")
        url = "http://localhost:5173/personal-assistant"
        pw(f"goto {url}")

    # Attendre le stepper + l'interface
    print("\nAttente du workflow (stepper → interface — jusqu'à 240s)...")
    interface_ready = wait_for_interface(timeout=240)

    if not interface_ready:
        print("  ERREUR: Timeout en attente de l'interface")
    else:
        print("  Interface prête !")

    # Récupérer le message de bienvenue
    print("\nMessage de bienvenue...")
    welcome = get_welcome_message()
    if welcome:
        print(f"  \"{welcome[:200]}{'...' if len(welcome) > 200 else ''}\"")
    else:
        print("  AVERTISSEMENT: pas de message de bienvenue trouvé")

    # Récupérer les outils du dock
    print("\nOutils dans le dock...")
    tools = get_dock_tools()
    for t in tools:
        print(f"  - {t}")
    if not tools:
        print("  AVERTISSEMENT: aucun outil dans le dock")

    # Vérifier les objectifs en DB
    print("\nObjectifs en DB...")
    objectifs = get_objectifs_from_db()
    for obj in objectifs:
        print(f"  #{obj['rang']}  {obj['objectif']}")
        print(f"       {obj['tool_type'] or '-'} | {obj['urgence']} | {obj['statut']}")
    if not objectifs:
        print("  AVERTISSEMENT: aucun objectif en DB")

    # Vérifier le maturity_level en DB
    print("\nVérification du maturity_level...")
    maturity = check_maturity_level(session_id)
    if maturity == 2:
        print(f"  OK: maturity_level = {maturity} (transition 1→2 réussie)")
    else:
        print(f"  AVERTISSEMENT: maturity_level = {maturity} (attendu: 2)")

    # Sauvegarder les résultats
    print("\nSauvegarde des résultats...")

    if objectifs:
        objectifs_path = RUN_DIR / "objectifs.json"
        with open(objectifs_path, "w", encoding="utf-8") as f:
            json.dump(objectifs, f, ensure_ascii=False, indent=2)
        print(f"  Objectifs: {objectifs_path}")

    if welcome:
        welcome_path = RUN_DIR / "welcome_message.txt"
        with open(welcome_path, "w", encoding="utf-8") as f:
            f.write(welcome)
        print(f"  Welcome: {welcome_path}")

    if tools:
        tools_path = RUN_DIR / "dock_tools.json"
        with open(tools_path, "w", encoding="utf-8") as f:
            json.dump(tools, f, ensure_ascii=False, indent=2)
        print(f"  Dock tools: {tools_path}")

    profile_path = RUN_DIR / "profile_input.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"  Profil input: {profile_path}")

    session_state = get_session_state(session_id)
    state_path = RUN_DIR / "session_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(session_state, f, ensure_ascii=False, indent=2)
    print(f"  État session: {state_path}")

    # Ne PAS restaurer le snapshot : on laisse la DB en l'état post-workflow
    # pour que l'interface reste fonctionnelle (objectifs, maturity_level=2, etc.)
    # Utiliser --restore-only pour restaurer manuellement si besoin.
    print("\nSnapshot DB conservé (pas de restauration automatique)")
    print(f"  Pour restaurer : python scripts/02_second_step_plan.py --restore-only")

    print(f"\n{'=' * 60}")
    print(f" Run terminé: {RUN_DIR}")
    print(f" maturity_level final: {maturity}")
    print(f" Objectifs: {len(objectifs)}")
    print(f" Dock tools: {len(tools)}")
    print(f" Interface: {'OK' if interface_ready else 'TIMEOUT'}")
    print("=" * 60)
    print("Navigateur ouvert pour inspection.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 2 onboarding — Workflow séquentiel"
    )
    parser.add_argument(
        "--restore-only",
        action="store_true",
        help="Restaure uniquement le snapshot DB sans relancer le workflow",
    )
    args = parser.parse_args()

    if args.restore_only:
        print("Restauration du snapshot DB...")
        restore_db()
        print("Done.")
    else:
        run()
