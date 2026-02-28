"""
Gestionnaire de sessions en mémoire pour Kameleon.
Maintient un dictionnaire de sessions actives et crée les Swarms Strands par session.
"""
import json
import uuid
from pathlib import Path

from backend.agents.factory import create_swarm

# Chemin vers le dossier de données seed
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SessionManager:
    """
    Gère les sessions utilisateur en mémoire.

    Chaque session contient :
    - Un identifiant unique
    - La persona résolue depuis le sous-domaine
    - Les données de seed chargées depuis les fichiers JSON
    - Un Swarm Strands dédié (1 swarm par session)
    - Le niveau de maturité de la persona (1-4)
    - Les widgets actifs dans la session
    """

    def __init__(self):
        self._sessions: dict = {}
        self._seed_data: dict = {}
        self._load_seed_data()

    def _load_seed_data(self):
        """
        Charge les données de seed depuis les fichiers JSON du dossier backend/data/.

        - Léa (freelance) : lea.json — projets, clients, finances
        - Marc (merchant) : marc.json — produits, stock, ventes
        - Sophie (creator) : pas de seed data (démarre avec un espace vide)
        """
        lea_path = _DATA_DIR / "lea.json"
        marc_path = _DATA_DIR / "marc.json"

        if lea_path.exists():
            with open(lea_path, "r", encoding="utf-8") as f:
                self._seed_data["freelance"] = json.load(f)
        else:
            self._seed_data["freelance"] = {}

        if marc_path.exists():
            with open(marc_path, "r", encoding="utf-8") as f:
                self._seed_data["merchant"] = json.load(f)
        else:
            self._seed_data["merchant"] = {}

        # Sophie démarre sans données — elle remplit son espace au fil de l'onboarding
        self._seed_data["creator"] = {}

    def get_or_create_session(self, session_id: str, persona: str) -> dict:
        """
        Retourne la session existante ou en crée une nouvelle.

        Args:
            session_id: Identifiant unique de session (UUID)
            persona: Type de persona ("creator" | "freelance" | "merchant")

        Returns:
            Dictionnaire de session avec swarm, seed_data, etc.
        """
        if session_id in self._sessions:
            return self._sessions[session_id]

        seed_data = self._seed_data.get(persona, {})

        session = {
            "session_id": session_id,
            "persona": persona,
            "seed_data": seed_data,
            "swarm": create_swarm(persona, seed_data),
            "maturity_level": 1,
            "active_widgets": [],
        }

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> dict | None:
        """
        Retourne la session existante ou None si elle n'existe pas.

        Args:
            session_id: Identifiant unique de session

        Returns:
            Dictionnaire de session ou None
        """
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str):
        """
        Supprime une session de la mémoire.

        Args:
            session_id: Identifiant unique de session à supprimer
        """
        self._sessions.pop(session_id, None)


# Singleton partagé par toute l'application
session_manager = SessionManager()
