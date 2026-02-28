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

_CREATE_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_CREATE_ADMIN_CHECKLIST_SQL = """
CREATE TABLE IF NOT EXISTS admin_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    url TEXT,
    done INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_CREATE_CALENDAR_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    titre TEXT NOT NULL,
    description TEXT,
    type TEXT DEFAULT 'action',
    done INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_CREATE_CRM_CLIENTS_SQL = """
CREATE TABLE IF NOT EXISTS crm_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    nom TEXT NOT NULL,
    email TEXT,
    telephone TEXT,
    secteur TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_CREATE_CRM_FACTURES_SQL = """
CREATE TABLE IF NOT EXISTS crm_factures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    client_id INTEGER,
    numero TEXT NOT NULL,
    montant REAL NOT NULL,
    devise TEXT DEFAULT 'EUR',
    date_emission TEXT,
    date_echeance TEXT,
    statut TEXT DEFAULT 'en_attente',
    description TEXT,
    items TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (client_id) REFERENCES crm_clients(id)
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
    Crée les tables sessions, messages et tools si elles n'existent pas encore.
    Idempotent — peut être appelé plusieurs fois sans erreur.
    """
    with _connect() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_MESSAGES_TABLE_SQL)
        conn.execute(_CREATE_ADMIN_CHECKLIST_SQL)
        conn.execute(_CREATE_CALENDAR_EVENTS_SQL)
        conn.execute(_CREATE_CRM_CLIENTS_SQL)
        conn.execute(_CREATE_CRM_FACTURES_SQL)
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
        persona: Type de persona ("creator" | "merchant")
        assistant_name: Nom choisi par l'utilisateur pour l'agent (peut être None)
        maturity_level: Niveau de maturité actuel (1-4)
        onboarding_data: Données collectées durant l'onboarding (sérialisées en JSON)
    """
    onboarding_json = json.dumps(onboarding_data or {}, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(_UPSERT_SQL, (session_id, persona, assistant_name, maturity_level, onboarding_json))
        conn.commit()


def save_message(session_id: str, role: str, content: str) -> None:
    """
    Insère un message dans la table messages.

    Args:
        session_id: Identifiant de session
        role: "user" ou "assistant"
        content: Contenu du message
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


def load_messages(session_id: str) -> list[dict]:
    """
    Charge tous les messages d'une session, triés par ordre chronologique.

    Args:
        session_id: Identifiant de session

    Returns:
        Liste de dicts {role, content, created_at}
    """
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        rows = cursor.fetchall()

    return [{"role": row[0], "content": row[1], "created_at": row[2]} for row in rows]


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


# =====================================================
# CRUD — Admin Checklist
# =====================================================

def save_admin_checklist(session_id: str, items: list[dict]) -> None:
    """Persiste la checklist admin (remplace l'existante pour la session)."""
    with _connect() as conn:
        conn.execute("DELETE FROM admin_checklist WHERE session_id = ?", (session_id,))
        for i, item in enumerate(items):
            conn.execute(
                "INSERT INTO admin_checklist (session_id, label, description, url, done, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, item.get("label", ""), item.get("description", ""),
                 item.get("url"), 1 if item.get("done") else 0, i),
            )
        conn.commit()


def load_admin_checklist(session_id: str) -> list[dict]:
    """Charge la checklist admin d'une session."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT id, label, description, url, done, sort_order FROM admin_checklist WHERE session_id = ? ORDER BY sort_order",
            (session_id,),
        )
        rows = cursor.fetchall()
    return [
        {"id": r[0], "label": r[1], "description": r[2], "url": r[3], "done": bool(r[4]), "sort_order": r[5]}
        for r in rows
    ]


def toggle_admin_item(item_id: int) -> bool:
    """Toggle done/undone pour un item admin. Retourne le nouveau statut."""
    with _connect() as conn:
        cursor = conn.execute("SELECT done FROM admin_checklist WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row is None:
            return False
        new_done = 0 if row[0] else 1
        conn.execute("UPDATE admin_checklist SET done = ? WHERE id = ?", (new_done, item_id))
        conn.commit()
    return bool(new_done)


# =====================================================
# CRUD — Calendar Events
# =====================================================

def save_calendar_events(session_id: str, events: list[dict]) -> None:
    """Persiste les events calendrier (remplace les existants pour la session)."""
    with _connect() as conn:
        conn.execute("DELETE FROM calendar_events WHERE session_id = ?", (session_id,))
        for ev in events:
            conn.execute(
                "INSERT INTO calendar_events (session_id, date, titre, description, type) VALUES (?, ?, ?, ?, ?)",
                (session_id, ev.get("date", ""), ev.get("titre", ""),
                 ev.get("description", ""), ev.get("type", "action")),
            )
        conn.commit()


def load_calendar_events(session_id: str) -> list[dict]:
    """Charge les events calendrier d'une session."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT id, date, titre, description, type, done FROM calendar_events WHERE session_id = ? ORDER BY date",
            (session_id,),
        )
        rows = cursor.fetchall()
    return [
        {"id": r[0], "date": r[1], "titre": r[2], "description": r[3], "type": r[4], "done": bool(r[5])}
        for r in rows
    ]


# =====================================================
# CRUD — CRM Clients & Factures
# =====================================================

def save_crm_client(session_id: str, client: dict) -> int:
    """Insère un client CRM et retourne son id."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO crm_clients (session_id, nom, email, telephone, secteur, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, client.get("nom", ""), client.get("email"),
             client.get("telephone"), client.get("secteur"), client.get("notes")),
        )
        conn.commit()
        return cursor.lastrowid


def save_crm_facture(session_id: str, facture: dict) -> int:
    """Insère une facture CRM et retourne son id."""
    items_json = json.dumps(facture.get("items", []), ensure_ascii=False) if facture.get("items") else None
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO crm_factures (session_id, client_id, numero, montant, devise, date_emission, date_echeance, statut, description, items) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, facture.get("client_id"), facture.get("numero", ""),
             facture.get("montant", 0), facture.get("devise", "EUR"),
             facture.get("date_emission"), facture.get("date_echeance"),
             facture.get("statut", "en_attente"), facture.get("description"),
             items_json),
        )
        conn.commit()
        return cursor.lastrowid


def load_crm_data(session_id: str) -> dict:
    """Charge clients et factures CRM d'une session."""
    with _connect() as conn:
        # Clients
        cursor = conn.execute(
            "SELECT id, nom, email, telephone, secteur, notes, created_at FROM crm_clients WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        clients = [
            {"id": r[0], "nom": r[1], "email": r[2], "telephone": r[3],
             "secteur": r[4], "notes": r[5], "created_at": r[6]}
            for r in cursor.fetchall()
        ]

        # Factures
        cursor = conn.execute(
            "SELECT id, client_id, numero, montant, devise, date_emission, date_echeance, statut, description, items FROM crm_factures WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        factures = [
            {"id": r[0], "client_id": r[1], "numero": r[2], "montant": r[3],
             "devise": r[4], "date_emission": r[5], "date_echeance": r[6],
             "statut": r[7], "description": r[8],
             "items": json.loads(r[9]) if r[9] else []}
            for r in cursor.fetchall()
        ]

    return {"clients": clients, "factures": factures}
