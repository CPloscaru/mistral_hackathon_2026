"""
Couche de persistance SQLite pour les sessions Kameleon.
Stocke les sessions entre les redémarrages du serveur.
"""
import json
import sqlite3
from pathlib import Path

# Chemin vers la base SQLite — à la racine du projet
DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "kameleon.db")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    persona         TEXT NOT NULL,
    assistant_name  TEXT,
    maturity_level  INTEGER DEFAULT 1,
    onboarding_data TEXT DEFAULT '{}'
)
"""

_UPSERT_SQL = """
INSERT INTO sessions (session_id, persona, assistant_name, maturity_level, onboarding_data)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(session_id) DO UPDATE SET
    persona         = excluded.persona,
    assistant_name  = excluded.assistant_name,
    maturity_level  = excluded.maturity_level,
    onboarding_data = excluded.onboarding_data
"""

_SELECT_SQL = """
SELECT session_id, persona, assistant_name, maturity_level, onboarding_data
FROM sessions
WHERE session_id = ?
"""


def _connect() -> sqlite3.Connection:
    """Ouvre une connexion SQLite vers DB_PATH."""
    return sqlite3.connect(DB_PATH, timeout=10)


def init_db() -> None:
    """
    Crée la table sessions si elle n'existe pas encore.
    Idempotent — peut être appelé plusieurs fois sans erreur.
    """
    with _connect() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()


def save_session(
    session_id: str,
    persona: str,
    assistant_name: str | None,
    maturity_level: int,
    onboarding_data: dict,
) -> None:
    """
    Insère ou met à jour une session dans SQLite (upsert).

    Args:
        session_id: Identifiant unique de session (UUID)
        persona: Type de persona ("creator" | "freelance" | "merchant")
        assistant_name: Nom choisi par l'utilisateur pour l'agent (peut être None)
        maturity_level: Niveau de maturité actuel (1-4)
        onboarding_data: Données collectées durant l'onboarding (sérialisées en JSON)
    """
    onboarding_json = json.dumps(onboarding_data or {}, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(_UPSERT_SQL, (session_id, persona, assistant_name, maturity_level, onboarding_json))
        conn.commit()


def load_session(session_id: str) -> dict | None:
    """
    Charge une session depuis SQLite.

    Args:
        session_id: Identifiant unique de session

    Returns:
        Dictionnaire de session ou None si inconnu
    """
    with _connect() as conn:
        cursor = conn.execute(_SELECT_SQL, (session_id,))
        row = cursor.fetchone()

    if row is None:
        return None

    return {
        "session_id": row[0],
        "persona": row[1],
        "assistant_name": row[2],
        "maturity_level": row[3],
        "onboarding_data": json.loads(row[4] or "{}"),
    }
