"""
Gestionnaire de sessions en mémoire pour Kameleon.
Maintient un dictionnaire de sessions actives et crée les Agents/Swarms Strands par session.
Persiste les sessions dans SQLite via backend.session.db.
"""
import json
import uuid
from pathlib import Path

from backend.agents.factory import create_swarm
from backend.agents.onboarding import create_onboarding_agent, create_onboarding_swarm
from backend.session import db

# Chemin vers le dossier de données seed
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SessionManager:
    """
    Gère les sessions utilisateur avec cache mémoire + persistance SQLite.

    Chaque session contient :
    - Un identifiant unique
    - La persona résolue depuis le sous-domaine
    - Les données de seed chargées depuis les fichiers JSON
    - Un Agent ou Swarm Strands dédié (1 par session) sous la clé "agent"
    - Le niveau de maturité de la persona (1-4)
    - Les widgets actifs dans la session
    - Le nom de l'assistant choisi par l'utilisateur
    """

    def __init__(self):
        self._sessions: dict = {}
        self._seed_data: dict = {}
        db.init_db()
        self._load_seed_data()

    def _load_seed_data(self):
        """
        Charge les données de seed depuis les fichiers JSON du dossier backend/data/.

        - Marc (merchant) : marc.json — produits, stock, ventes
        - Sophie (creator) : pas de seed data (démarre avec un espace vide)
        """
        marc_path = _DATA_DIR / "marc.json"

        if marc_path.exists():
            with open(marc_path, "r", encoding="utf-8") as f:
                self._seed_data["merchant"] = json.load(f)
        else:
            self._seed_data["merchant"] = {}

        # Sophie démarre sans données — elle remplit son espace au fil de l'onboarding
        self._seed_data["creator"] = {}

    def _create_agent_for_persona(self, persona: str, seed_data: dict, maturity_level: int):
        """
        Crée l'agent/swarm approprié selon la persona et le niveau de maturité.

        - Creator (Sophie) en onboarding (maturity=1) → Agent conversationnel
        - Tous les autres cas → Swarm standard day-to-day
        """
        if persona == "creator" and maturity_level == 1:
            return create_onboarding_agent()
        return create_swarm(persona, seed_data)

    def get_or_create_session(self, session_id: str, persona: str) -> dict:
        """
        Retourne la session existante (mémoire ou SQLite) ou en crée une nouvelle.

        Ordre de recherche :
        1. Cache mémoire (rapide)
        2. SQLite (persistance entre redémarrages)
        3. Nouvelle session (première visite)

        Args:
            session_id: Identifiant unique de session (UUID)
            persona: Type de persona ("creator" | "merchant")

        Returns:
            Dictionnaire de session avec agent, seed_data, etc.
        """
        # 1. Cache mémoire
        if session_id in self._sessions:
            return self._sessions[session_id]

        # 2. Essai depuis SQLite
        db_record = db.load_session(session_id)
        if db_record is not None:
            # Si la persona stockée ne correspond pas à la persona demandée,
            # ignorer l'enregistrement SQLite pour éviter les cross-subdomain contaminations
            # (ex: même session_id utilisée sur sophie.localhost puis marc.localhost)
            if db_record["persona"] != persona:
                pass  # Fall through to create a new session
            else:
                seed_data = self._seed_data.get(db_record["persona"], {})
                agent = self._create_agent_for_persona(
                    db_record["persona"], seed_data, db_record["maturity_level"]
                )
                session = {
                    "session_id": db_record["session_id"],
                    "persona": db_record["persona"],
                    "seed_data": seed_data,
                    "agent": agent,
                    "maturity_level": db_record["maturity_level"],
                    "active_widgets": [],
                    "assistant_name": db_record["assistant_name"],
                }
                self._sessions[session_id] = session
                return session

        # 3. Nouvelle session
        seed_data = self._seed_data.get(persona, {})
        agent = self._create_agent_for_persona(persona, seed_data, 1)
        session = {
            "session_id": session_id,
            "persona": persona,
            "seed_data": seed_data,
            "agent": agent,
            "maturity_level": 1,
            "active_widgets": [],
            "assistant_name": None,
        }

        self._sessions[session_id] = session
        db.save_session(
            session_id=session_id,
            persona=persona,
            assistant_name=None,
            maturity_level=1,
            onboarding_data={},
        )
        return session

    def get_session(self, session_id: str) -> dict | None:
        """
        Retourne la session existante en mémoire ou None.

        N'interroge pas SQLite — consulte uniquement le cache mémoire.

        Args:
            session_id: Identifiant unique de session

        Returns:
            Dictionnaire de session ou None
        """
        return self._sessions.get(session_id)

    def update_session_state(
        self,
        session_id: str,
        assistant_name: str | None = None,
        maturity_level: int | None = None,
        onboarding_data: dict | None = None,
    ) -> None:
        """
        Met à jour l'état d'une session en mémoire ET persiste en SQLite.

        Args:
            session_id: Identifiant unique de session
            assistant_name: Nouveau nom de l'assistant (None = pas de changement)
            maturity_level: Nouveau niveau de maturité (None = pas de changement)
            onboarding_data: Nouvelles données d'onboarding (None = pas de changement)
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

        # Persistance SQLite
        db.save_session(
            session_id=session_id,
            persona=session["persona"],
            assistant_name=session.get("assistant_name"),
            maturity_level=session["maturity_level"],
            onboarding_data=session.get("onboarding_data", {}),
        )

    def swap_to_swarm(self, session_id: str) -> dict:
        """
        Remplace l'Agent conversationnel par le Swarm onboarding dans la session.

        Appelé quand le backend détecte onboarding_data dans la session et que
        le prochain message doit déclencher le Swarm one-shot (plan SMART).

        Args:
            session_id: Identifiant unique de session

        Returns:
            Session mise à jour avec le Swarm comme agent
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} introuvable")

        swarm = create_onboarding_swarm()
        session["agent"] = swarm
        return session

    def delete_session(self, session_id: str):
        """
        Supprime une session de la mémoire.

        Args:
            session_id: Identifiant unique de session à supprimer
        """
        self._sessions.pop(session_id, None)


# Singleton partagé par toute l'application
session_manager = SessionManager()
