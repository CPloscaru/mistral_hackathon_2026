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
    session_id        TEXT PRIMARY KEY,
    persona           TEXT NOT NULL,
    assistant_name    TEXT,
    maturity_level    INTEGER DEFAULT 1,
    onboarding_data   TEXT DEFAULT '{}',
    active_components TEXT DEFAULT '[]',
    statut_juridique  TEXT
)
"""

_CREATE_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    chat_type   TEXT DEFAULT 'main',
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

_CREATE_BUDGET_DATA_SQL = """
CREATE TABLE IF NOT EXISTS budget_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    data TEXT NOT NULL,
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

_CREATE_OBJECTIFS_SQL = """
CREATE TABLE IF NOT EXISTS objectifs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rang        INTEGER NOT NULL,
    objectif    TEXT NOT NULL,
    urgence     TEXT NOT NULL,
    impact      TEXT NOT NULL,
    justification TEXT,
    tool_type   TEXT,
    raison      TEXT,
    statut      TEXT DEFAULT 'actif',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
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

_CREATE_CRM_RELANCES_SQL = """
CREATE TABLE IF NOT EXISTS crm_relances (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    facture_id    INTEGER NOT NULL,
    client_id     INTEGER NOT NULL,
    objet         TEXT NOT NULL,
    corps         TEXT NOT NULL,
    statut        TEXT DEFAULT 'brouillon',
    date_creation TEXT DEFAULT (datetime('now')),
    date_envoi    TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (facture_id) REFERENCES crm_factures(id),
    FOREIGN KEY (client_id) REFERENCES crm_clients(id)
)
"""

_CREATE_ROADMAP_SQL = """
CREATE TABLE IF NOT EXISTS roadmap (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    phase_index    INTEGER NOT NULL,
    titre          TEXT NOT NULL,
    objectif       TEXT,
    actions        TEXT DEFAULT '[]',
    statut         TEXT DEFAULT 'future',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_CREATE_ROADMAP_META_SQL = """
CREATE TABLE IF NOT EXISTS roadmap_meta (
    session_id     TEXT PRIMARY KEY,
    objectif_smart TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_CREATE_PREVISIONS_SQL = """
CREATE TABLE IF NOT EXISTS previsions_financieres (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL UNIQUE,
    objectif_net        REAL NOT NULL,
    ca_brut_cible       REAL NOT NULL,
    taux_cotisations    REAL NOT NULL,
    cotisations_montant REAL,
    ca_actuel           REAL DEFAULT 0,
    ca_manquant         REAL DEFAULT 0,
    tjm_moyen           REAL,
    missions_restantes  INTEGER,
    jours_restants      INTEGER,
    details             TEXT DEFAULT '{}',
    source_cotisations  TEXT,
    statut_juridique    TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""

_UPSERT_SQL = """
INSERT INTO sessions (session_id, persona, assistant_name, maturity_level, onboarding_data, active_components, statut_juridique)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(session_id) DO UPDATE SET
    persona           = excluded.persona,
    assistant_name    = excluded.assistant_name,
    maturity_level    = excluded.maturity_level,
    onboarding_data   = excluded.onboarding_data,
    active_components = excluded.active_components,
    statut_juridique  = excluded.statut_juridique
"""

_SELECT_SQL = """
SELECT session_id, persona, assistant_name, maturity_level, onboarding_data, active_components, statut_juridique
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
        conn.execute(_CREATE_BUDGET_DATA_SQL)
        conn.execute(_CREATE_CRM_CLIENTS_SQL)
        conn.execute(_CREATE_CRM_FACTURES_SQL)
        conn.execute(_CREATE_OBJECTIFS_SQL)
        conn.execute(_CREATE_CRM_RELANCES_SQL)
        conn.execute(_CREATE_ROADMAP_SQL)
        conn.execute(_CREATE_ROADMAP_META_SQL)
        conn.execute(_CREATE_PREVISIONS_SQL)
        # Migration : ajouter active_components si absente (DB existante)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN active_components TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # colonne existe déjà
        # Migration : ajouter chat_type si absente (DB existante)
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN chat_type TEXT DEFAULT 'main'")
        except sqlite3.OperationalError:
            pass  # colonne existe déjà
        # Migration : ajouter statut_juridique si absente (DB existante)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN statut_juridique TEXT")
        except sqlite3.OperationalError:
            pass  # colonne existe déjà
        conn.commit()


def save_session(
    session_id: str,
    persona: str,
    assistant_name: str | None,
    maturity_level: int,
    onboarding_data: dict,
    active_components: list | None = None,
    statut_juridique: str | None = None,
) -> None:
    """
    Insère ou met à jour une session dans SQLite (upsert).

    Args:
        session_id: Identifiant unique de session (UUID)
        persona: Type de persona ("creator" | "merchant")
        assistant_name: Nom choisi par l'utilisateur pour l'agent (peut être None)
        maturity_level: Niveau de maturité actuel (1-4)
        onboarding_data: Données collectées durant l'onboarding (sérialisées en JSON)
        active_components: Composants UI actifs (sérialisés en JSON)
        statut_juridique: Statut juridique choisi (micro-entreprise, SASU, etc.)
    """
    onboarding_json = json.dumps(onboarding_data or {}, ensure_ascii=False)
    components_json = json.dumps(active_components or [], ensure_ascii=False)
    with _connect() as conn:
        conn.execute(_UPSERT_SQL, (session_id, persona, assistant_name, maturity_level, onboarding_json, components_json, statut_juridique))
        conn.commit()


def save_message(session_id: str, role: str, content: str, chat_type: str = "main") -> None:
    """
    Insère un message dans la table messages.

    Args:
        session_id: Identifiant de session
        role: "user" ou "assistant"
        content: Contenu du message
        chat_type: Type de chat ("main", "conseils", etc.)
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, chat_type) VALUES (?, ?, ?, ?)",
            (session_id, role, content, chat_type),
        )
        conn.commit()


def load_messages(session_id: str, chat_type: str | None = None) -> list[dict]:
    """
    Charge les messages d'une session, triés par ordre chronologique.

    Args:
        session_id: Identifiant de session
        chat_type: Si fourni, filtre par type de chat

    Returns:
        Liste de dicts {role, content, created_at}
    """
    with _connect() as conn:
        if chat_type is not None:
            cursor = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? AND chat_type = ? ORDER BY id ASC",
                (session_id, chat_type),
            )
        else:
            cursor = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
        rows = cursor.fetchall()

    return [{"role": row[0], "content": row[1], "created_at": row[2]} for row in rows]


def load_active_session() -> dict | None:
    """
    Charge la dernière session créée (la plus récente par rowid).

    Returns:
        Dictionnaire de session ou None si aucune session n'existe
    """
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT session_id, persona, assistant_name, maturity_level, onboarding_data, active_components, statut_juridique "
            "FROM sessions ORDER BY rowid DESC LIMIT 1"
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return {
        "session_id": row[0],
        "persona": row[1],
        "assistant_name": row[2],
        "maturity_level": row[3],
        "onboarding_data": json.loads(row[4] or "{}"),
        "active_components": json.loads(row[5] or "[]") if len(row) > 5 else [],
        "statut_juridique": row[6] if len(row) > 6 else None,
    }


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
        "active_components": json.loads(row[5] or "[]") if len(row) > 5 else [],
        "statut_juridique": row[6] if len(row) > 6 else None,
    }


# =====================================================
# CRUD — Statut juridique
# =====================================================

def update_statut_juridique(session_id: str, statut: str) -> bool:
    """Met à jour le statut juridique d'une session.

    Returns:
        True si la session existait et a été mise à jour.
    """
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET statut_juridique = ? WHERE session_id = ?",
            (statut, session_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def get_statut_juridique(session_id: str) -> str | None:
    """Retourne le statut juridique d'une session, ou None."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT statut_juridique FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
    return row[0] if row else None


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
# CRUD — Budget Data
# =====================================================

def save_budget_data(session_id: str, budget_data: dict) -> None:
    """Persiste le budget prévisionnel (upsert — remplace l'existant pour la session)."""
    data_json = json.dumps(budget_data, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO budget_data (session_id, data) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET data = excluded.data",
            (session_id, data_json),
        )
        conn.commit()


def load_budget_data(session_id: str) -> dict | None:
    """Charge le budget prévisionnel d'une session."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT data FROM budget_data WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return json.loads(row[0])


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


# =====================================================
# CRUD — Objectifs
# =====================================================

def save_objectifs(objectifs: list[dict]) -> list[int]:
    """Persiste une liste d'objectifs (remplace tous les existants).

    Returns:
        Liste des ids insérés.
    """
    ids = []
    with _connect() as conn:
        conn.execute("DELETE FROM objectifs")
        for obj in objectifs:
            cursor = conn.execute(
                "INSERT INTO objectifs (rang, objectif, urgence, impact, justification, tool_type, raison) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    obj.get("rang", 0),
                    obj.get("objectif", ""),
                    obj.get("urgence", "moyenne"),
                    obj.get("impact", "moyen"),
                    obj.get("justification"),
                    obj.get("tool_type"),
                    obj.get("raison"),
                ),
            )
            ids.append(cursor.lastrowid)
        conn.commit()
    return ids


def load_objectifs() -> list[dict]:
    """Charge tous les objectifs, triés par rang."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT id, rang, objectif, urgence, impact, justification, tool_type, raison, statut "
            "FROM objectifs ORDER BY rang",
        )
        rows = cursor.fetchall()
    return [
        {
            "id": r[0], "rang": r[1], "objectif": r[2], "urgence": r[3],
            "impact": r[4], "justification": r[5], "tool_type": r[6],
            "raison": r[7], "statut": r[8],
        }
        for r in rows
    ]


def get_objectif(objectif_id: int) -> dict | None:
    """Charge un objectif par son id."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT id, rang, objectif, urgence, impact, justification, tool_type, raison, statut "
            "FROM objectifs WHERE id = ?",
            (objectif_id,),
        )
        r = cursor.fetchone()
    if r is None:
        return None
    return {
        "id": r[0], "rang": r[1], "objectif": r[2], "urgence": r[3],
        "impact": r[4], "justification": r[5], "tool_type": r[6],
        "raison": r[7], "statut": r[8],
    }


def update_objectif(objectif_id: int, **fields) -> bool:
    """Met à jour un objectif. Champs autorisés : rang, objectif, urgence, impact,
    justification, tool_type, raison, statut.

    Returns:
        True si l'objectif a été trouvé et modifié.
    """
    allowed = {"rang", "objectif", "urgence", "impact", "justification", "tool_type", "raison", "statut"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = "datetime('now')"

    set_clause = ", ".join(
        f"{k} = {v}" if k == "updated_at" else f"{k} = ?"
        for k, v in updates.items()
    )
    values = [v for k, v in updates.items() if k != "updated_at"]
    values.append(objectif_id)

    with _connect() as conn:
        cursor = conn.execute(
            f"UPDATE objectifs SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
    return cursor.rowcount > 0


def delete_objectif(objectif_id: int) -> bool:
    """Supprime un objectif par son id.

    Returns:
        True si l'objectif existait et a été supprimé.
    """
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM objectifs WHERE id = ?", (objectif_id,))
        conn.commit()
    return cursor.rowcount > 0


def create_objectif(
    rang: int,
    objectif: str,
    urgence: str,
    impact: str,
    justification: str | None = None,
    tool_type: str | None = None,
    raison: str | None = None,
) -> int:
    """Crée un objectif unique et retourne son id."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO objectifs (rang, objectif, urgence, impact, justification, tool_type, raison) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rang, objectif, urgence, impact, justification, tool_type, raison),
        )
        conn.commit()
    return cursor.lastrowid


# =====================================================
# CRUD — CRM Relances
# =====================================================

def save_relance(session_id: str, facture_id: int, client_id: int, objet: str, corps: str) -> int:
    """Crée un brouillon de relance et retourne son id."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO crm_relances (session_id, facture_id, client_id, objet, corps) VALUES (?, ?, ?, ?, ?)",
            (session_id, facture_id, client_id, objet, corps),
        )
        conn.commit()
    return cursor.lastrowid


def load_relances(session_id: str, facture_id: int | None = None) -> list[dict]:
    """Charge les relances d'une session, optionnellement filtrées par facture."""
    with _connect() as conn:
        if facture_id is not None:
            cursor = conn.execute(
                "SELECT id, session_id, facture_id, client_id, objet, corps, statut, date_creation, date_envoi "
                "FROM crm_relances WHERE session_id = ? AND facture_id = ? ORDER BY id DESC",
                (session_id, facture_id),
            )
        else:
            cursor = conn.execute(
                "SELECT id, session_id, facture_id, client_id, objet, corps, statut, date_creation, date_envoi "
                "FROM crm_relances WHERE session_id = ? ORDER BY id DESC",
                (session_id,),
            )
        rows = cursor.fetchall()
    return [
        {
            "id": r[0], "session_id": r[1], "facture_id": r[2], "client_id": r[3],
            "objet": r[4], "corps": r[5], "statut": r[6],
            "date_creation": r[7], "date_envoi": r[8],
        }
        for r in rows
    ]


def mark_relance_sent(relance_id: int) -> bool:
    """Marque une relance comme envoyée."""
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE crm_relances SET statut = 'envoyee', date_envoi = datetime('now') WHERE id = ? AND statut = 'brouillon'",
            (relance_id,),
        )
        conn.commit()
    return cursor.rowcount > 0


def get_relance(relance_id: int) -> dict | None:
    """Charge une relance par son id."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT id, session_id, facture_id, client_id, objet, corps, statut, date_creation, date_envoi "
            "FROM crm_relances WHERE id = ?",
            (relance_id,),
        )
        r = cursor.fetchone()
    if r is None:
        return None
    return {
        "id": r[0], "session_id": r[1], "facture_id": r[2], "client_id": r[3],
        "objet": r[4], "corps": r[5], "statut": r[6],
        "date_creation": r[7], "date_envoi": r[8],
    }


def delete_relance(relance_id: int) -> bool:
    """Supprime une relance (brouillon uniquement)."""
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM crm_relances WHERE id = ? AND statut = 'brouillon'",
            (relance_id,),
        )
        conn.commit()
    return cursor.rowcount > 0


def update_relance(relance_id: int, objet: str | None = None, corps: str | None = None) -> bool:
    """Met à jour l'objet et/ou le corps d'une relance brouillon."""
    updates = {}
    if objet is not None:
        updates["objet"] = objet
    if corps is not None:
        updates["corps"] = corps
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [relance_id]
    with _connect() as conn:
        cursor = conn.execute(
            f"UPDATE crm_relances SET {set_clause} WHERE id = ? AND statut = 'brouillon'",
            values,
        )
        conn.commit()
    return cursor.rowcount > 0


# =====================================================
# CRUD — Roadmap
# =====================================================

def save_roadmap(session_id: str, phases: list[dict], objectif_smart: str) -> None:
    """Persiste une roadmap complète (remplace les phases existantes)."""
    with _connect() as conn:
        conn.execute("DELETE FROM roadmap WHERE session_id = ?", (session_id,))
        for i, phase in enumerate(phases):
            actions_json = json.dumps(phase.get("actions", []), ensure_ascii=False)
            conn.execute(
                "INSERT INTO roadmap (session_id, phase_index, titre, objectif, actions, statut) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, i, phase.get("titre", ""), phase.get("objectif", ""),
                 actions_json, phase.get("statut", "future")),
            )
        conn.execute(
            "INSERT INTO roadmap_meta (session_id, objectif_smart) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET objectif_smart = excluded.objectif_smart",
            (session_id, objectif_smart),
        )
        conn.commit()


def load_roadmap(session_id: str) -> dict:
    """Charge la roadmap d'une session (phases + objectif_smart)."""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT phase_index, titre, objectif, actions, statut FROM roadmap WHERE session_id = ? ORDER BY phase_index",
            (session_id,),
        )
        phases = [
            {
                "phase_index": r[0], "titre": r[1], "objectif": r[2],
                "actions": json.loads(r[3]) if r[3] else [], "statut": r[4],
            }
            for r in cursor.fetchall()
        ]

        cursor = conn.execute("SELECT objectif_smart FROM roadmap_meta WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        objectif_smart = row[0] if row else ""

    return {"phases": phases, "objectif_smart": objectif_smart}


def update_roadmap_phase(session_id: str, phase_index: int, **fields) -> bool:
    """Met à jour une phase de la roadmap."""
    allowed = {"titre", "objectif", "actions", "statut"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    if "actions" in updates and isinstance(updates["actions"], list):
        updates["actions"] = json.dumps(updates["actions"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session_id, phase_index]

    with _connect() as conn:
        cursor = conn.execute(
            f"UPDATE roadmap SET {set_clause} WHERE session_id = ? AND phase_index = ?",
            values,
        )
        conn.commit()
    return cursor.rowcount > 0


def add_roadmap_phase(session_id: str, titre: str, objectif: str, actions: list) -> int:
    """Ajoute une phase à la fin de la roadmap."""
    actions_json = json.dumps(actions, ensure_ascii=False)
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT MAX(phase_index) FROM roadmap WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        next_index = (row[0] + 1) if row and row[0] is not None else 0
        cursor = conn.execute(
            "INSERT INTO roadmap (session_id, phase_index, titre, objectif, actions) VALUES (?, ?, ?, ?, ?)",
            (session_id, next_index, titre, objectif, actions_json),
        )
        conn.commit()
    return next_index


def remove_roadmap_phase(session_id: str, phase_index: int) -> bool:
    """Supprime une phase et renumérote les suivantes."""
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM roadmap WHERE session_id = ? AND phase_index = ?",
            (session_id, phase_index),
        )
        if cursor.rowcount == 0:
            return False
        # Renumeroter les phases suivantes
        conn.execute(
            "UPDATE roadmap SET phase_index = phase_index - 1 WHERE session_id = ? AND phase_index > ?",
            (session_id, phase_index),
        )
        conn.commit()
    return True


# =====================================================
# CRUD — Prévisions Financières
# =====================================================

def save_previsions(session_id: str, previsions: dict) -> int:
    """Persiste les prévisions financières (upsert)."""
    details_json = json.dumps(previsions.get("details", {}), ensure_ascii=False)
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO previsions_financieres
               (session_id, objectif_net, ca_brut_cible, taux_cotisations, cotisations_montant,
                ca_actuel, ca_manquant, tjm_moyen, missions_restantes, jours_restants,
                details, source_cotisations, statut_juridique)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                objectif_net = excluded.objectif_net,
                ca_brut_cible = excluded.ca_brut_cible,
                taux_cotisations = excluded.taux_cotisations,
                cotisations_montant = excluded.cotisations_montant,
                ca_actuel = excluded.ca_actuel,
                ca_manquant = excluded.ca_manquant,
                tjm_moyen = excluded.tjm_moyen,
                missions_restantes = excluded.missions_restantes,
                jours_restants = excluded.jours_restants,
                details = excluded.details,
                source_cotisations = excluded.source_cotisations,
                statut_juridique = excluded.statut_juridique,
                created_at = datetime('now')
            """,
            (
                session_id,
                previsions.get("objectif_net", 0),
                previsions.get("ca_brut_cible", 0),
                previsions.get("taux_cotisations", 0),
                previsions.get("cotisations_montant"),
                previsions.get("ca_actuel", 0),
                previsions.get("ca_manquant", 0),
                previsions.get("tjm_moyen"),
                previsions.get("missions_restantes"),
                previsions.get("jours_restants"),
                details_json,
                previsions.get("source_cotisations"),
                previsions.get("statut_juridique"),
            ),
        )
        conn.commit()
    return cursor.lastrowid


def load_previsions(session_id: str) -> dict | None:
    """Charge les prévisions financières d'une session."""
    with _connect() as conn:
        cursor = conn.execute(
            """SELECT objectif_net, ca_brut_cible, taux_cotisations, cotisations_montant,
                      ca_actuel, ca_manquant, tjm_moyen, missions_restantes, jours_restants,
                      details, source_cotisations, statut_juridique, created_at
               FROM previsions_financieres WHERE session_id = ?""",
            (session_id,),
        )
        r = cursor.fetchone()
    if r is None:
        return None
    return {
        "objectif_net": r[0],
        "ca_brut_cible": r[1],
        "taux_cotisations": r[2],
        "cotisations_montant": r[3],
        "ca_actuel": r[4],
        "ca_manquant": r[5],
        "tjm_moyen": r[6],
        "missions_restantes": r[7],
        "jours_restants": r[8],
        "details": json.loads(r[9]) if r[9] else {},
        "source_cotisations": r[10],
        "statut_juridique": r[11],
        "created_at": r[12],
    }
