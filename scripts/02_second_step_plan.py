"""
Test automatisé — Phase 2 de l'onboarding (Swarm one-shot plan SMART).

Lit le profil JSON du dernier run 01_first_step_onboarding, snapshot la DB,
injecte les données d'onboarding dans une nouvelle session, ouvre
/personal-assistant et attend le plan_ready structuré.

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


def wait_for_plan_display(timeout: int = 180) -> str:
    """
    Poll le DOM : attend que l'objectif SMART s'affiche dans .smart-display__objectif
    (après le spinner + typewriter).
    """
    start = time.time()
    time.sleep(5)  # Au moins 3s de spinner + marge

    while time.time() - start < timeout:
        # Vérifier si on est encore en phase spinner
        has_spinner = pw_eval(
            "!!document.querySelector('.spinner-overlay')"
        )
        if has_spinner == "true":
            time.sleep(2)
            continue

        # Vérifier si l'objectif est affiché
        objectif = pw_eval(
            "document.querySelector('.smart-display__objectif')?.textContent || ''"
        ).strip()

        if objectif and len(objectif) > 10:
            return objectif

        time.sleep(2)

    return "[TIMEOUT]"


def get_plan_json_from_dom() -> dict | None:
    """
    Tente de récupérer les données du plan depuis le DOM.
    Lit les phases et prochaines étapes depuis les éléments affichés.
    """
    try:
        # Lire l'objectif
        objectif = pw_eval(
            "document.querySelector('.smart-display__objectif')?.textContent || ''"
        ).strip()

        # Lire les phases
        phases_json = pw_eval(
            "[...document.querySelectorAll('.smart-display__phase')].map(p => ({"
            "titre: p.querySelector('.smart-display__phase-title')?.textContent || '',"
            "objectif: p.querySelector('.smart-display__phase-objectif')?.textContent || '',"
            "actions: [...p.querySelectorAll('.smart-display__phase-actions li')].map(a => a.textContent)"
            "}))"
        )

        # Lire les prochaines étapes
        etapes_json = pw_eval(
            "[...document.querySelectorAll('.smart-display__etapes li')].map(e => e.textContent)"
        )

        plan = {"objectif_smart": objectif}

        try:
            plan["phases"] = json.loads(phases_json)
        except (json.JSONDecodeError, TypeError):
            plan["phases"] = []

        try:
            plan["prochaines_etapes"] = json.loads(etapes_json)
        except (json.JSONDecodeError, TypeError):
            plan["prochaines_etapes"] = []

        return plan if objectif else None
    except Exception as e:
        print(f"  ERREUR lecture DOM: {e}")
        return None


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
    print(" → /personal-assistant avec spinner + objectif SMART")
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

    # 5. Ouvrir le navigateur directement sur /personal-assistant
    print("\n5. Ouverture du navigateur sur /personal-assistant...")
    url = f"http://sophie.localhost:5173/personal-assistant?session_id={session_id}"
    pw(f"open {url} --browser chrome --headed")

    # 6. Attendre l'affichage de l'objectif SMART (après spinner + typewriter)
    print("\n6. Attente de l'objectif SMART (spinner ≥ 3s + typewriter — jusqu'à 180s)...")
    objectif_text = wait_for_plan_display(timeout=180)

    if objectif_text == "[TIMEOUT]":
        print("  ERREUR: Timeout en attente de l'objectif SMART")
    else:
        print(f"\n  Objectif reçu ({len(objectif_text)} chars):")
        print(f"  \"{objectif_text[:200]}{'...' if len(objectif_text) > 200 else ''}\"")

    # 7. Récupérer le plan structuré depuis le DOM
    print("\n7. Extraction du plan structuré depuis le DOM...")
    plan_data = get_plan_json_from_dom()
    if plan_data:
        print(f"  Plan extrait: {len(plan_data.get('phases', []))} phases, "
              f"{len(plan_data.get('prochaines_etapes', []))} étapes")
    else:
        print("  AVERTISSEMENT: plan structuré non trouvable dans le DOM")

    # 8. Vérifier le maturity_level en DB
    print("\n8. Vérification du maturity_level...")
    maturity = check_maturity_level(session_id)
    if maturity == 2:
        print(f"  OK: maturity_level = {maturity} (transition 1→2 réussie)")
    else:
        print(f"  AVERTISSEMENT: maturity_level = {maturity} (attendu: 2)")

    # 9. Sauvegarder les résultats
    print("\n9. Sauvegarde des résultats...")

    # Plan structuré JSON
    if plan_data:
        plan_path = RUN_DIR / "plan.json"
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)
        print(f"  Plan JSON: {plan_path}")

    # Plan texte (objectif seul)
    plan_txt_path = RUN_DIR / "plan.txt"
    with open(plan_txt_path, "w", encoding="utf-8") as f:
        f.write(objectif_text)
    print(f"  Plan texte: {plan_txt_path}")

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
    print(f" Plan structuré: {'OK' if plan_data else 'NON'}")
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
