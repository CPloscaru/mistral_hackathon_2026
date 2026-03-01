"""
Gestionnaire de sessions en mémoire pour Kameleon.
Simplifié : un seul assistant personnel par utilisateur, sans personas.
Persiste les sessions dans SQLite via backend.session.db.
"""
import logging

from backend.session import db

logger = logging.getLogger("kameleon.session")


class SessionManager:
    """
    Gère la session utilisateur unique avec cache mémoire + persistance SQLite.

    Chaque session contient :
    - Un identifiant unique
    - Les données d'onboarding collectées
    - Le niveau de maturité (1 = onboarding, 2 = post-onboarding)
    - Les composants UI actifs (A2UI)
    - Le nom de l'assistant choisi par l'utilisateur
    """

    def __init__(self):
        self._sessions: dict = {}
        db.init_db()

    def get_or_create_session(self, session_id: str) -> dict:
        """
        Retourne la session existante (mémoire ou SQLite) ou en crée une nouvelle.

        Args:
            session_id: Identifiant unique de session

        Returns:
            Dictionnaire de session
        """
        # 1. Cache mémoire
        if session_id in self._sessions:
            return self._sessions[session_id]

        # 2. Essai depuis SQLite
        db_record = db.load_session(session_id)
        if db_record is not None:
            session = {
                "session_id": db_record["session_id"],
                "maturity_level": db_record["maturity_level"],
                "active_components": db_record.get("active_components", []),
                "assistant_name": db_record["assistant_name"],
                "onboarding_data": db_record.get("onboarding_data", {}),
                "statut_juridique": db_record.get("statut_juridique"),
            }
            self._sessions[session_id] = session
            return session

        # 3. Nouvelle session
        session = {
            "session_id": session_id,
            "maturity_level": 1,
            "active_components": [],
            "assistant_name": None,
            "onboarding_data": {},
            "statut_juridique": None,
        }

        self._sessions[session_id] = session
        db.save_session(
            session_id=session_id,
            persona="default",
            assistant_name=None,
            maturity_level=1,
            onboarding_data={},
        )
        return session

    def get_session(self, session_id: str) -> dict | None:
        """Retourne la session en mémoire ou None."""
        return self._sessions.get(session_id)

    def update_session_state(
        self,
        session_id: str,
        assistant_name: str | None = None,
        maturity_level: int | None = None,
        onboarding_data: dict | None = None,
        active_components: list | None = None,
        statut_juridique: str | None = None,
    ) -> None:
        """
        Met à jour l'état d'une session en mémoire ET persiste en SQLite.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return

        if assistant_name is not None:
            session["assistant_name"] = assistant_name
        if maturity_level is not None:
            session["maturity_level"] = maturity_level
        if onboarding_data is not None:
            session["onboarding_data"] = onboarding_data
        if active_components is not None:
            session["active_components"] = active_components
        if statut_juridique is not None:
            session["statut_juridique"] = statut_juridique

        # Persistance SQLite
        db.save_session(
            session_id=session_id,
            persona="default",
            assistant_name=session.get("assistant_name"),
            maturity_level=session["maturity_level"],
            onboarding_data=session.get("onboarding_data", {}),
            active_components=session.get("active_components", []),
            statut_juridique=session.get("statut_juridique"),
        )

    def delete_session(self, session_id: str):
        """Supprime une session de la mémoire."""
        self._sessions.pop(session_id, None)


# Singleton partagé par toute l'application
session_manager = SessionManager()
