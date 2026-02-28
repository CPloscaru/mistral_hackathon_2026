"""
Tests de gestion des sessions utilisateur.
Vérifie la création, la persistance et la suppression des sessions.
Les appels à create_swarm sont mockés pour éviter les appels à l'API Mistral.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock


@pytest.fixture
def gestionnaire_session():
    """Retourne un SessionManager isolé avec create_swarm mocké."""
    with patch("backend.agents.factory.MistralModel"), \
         patch("backend.agents.factory.Agent") as mock_agent, \
         patch("backend.agents.factory.Swarm") as mock_swarm:

        mock_agent.return_value = MagicMock(name="agent_mock")
        mock_swarm.return_value = MagicMock(name="swarm_mock")

        from backend.session.manager import SessionManager
        manager = SessionManager()
        yield manager


def test_creation_session(gestionnaire_session):
    """Une nouvelle session doit être créée avec la persona correcte."""
    session_id = str(uuid.uuid4())
    session = gestionnaire_session.get_or_create_session(session_id, "freelance")

    assert session["session_id"] == session_id
    assert session["persona"] == "freelance"
    assert session["maturity_level"] == 1
    assert isinstance(session["active_widgets"], list)


def test_session_persistance(gestionnaire_session):
    """Deux appels avec le même session_id doivent retourner le même objet."""
    session_id = str(uuid.uuid4())

    session1 = gestionnaire_session.get_or_create_session(session_id, "freelance")
    session2 = gestionnaire_session.get_or_create_session(session_id, "freelance")

    assert session1 is session2


def test_session_lea_avec_seed_data(gestionnaire_session):
    """La session Léa (freelance) doit contenir des données de seed non vides."""
    session_id = str(uuid.uuid4())
    session = gestionnaire_session.get_or_create_session(session_id, "freelance")

    assert session["seed_data"] != {}
    assert len(session["seed_data"]) > 0


def test_session_sophie_sans_seed_data(gestionnaire_session):
    """La session Sophie (creator) doit avoir des données de seed vides."""
    session_id = str(uuid.uuid4())
    session = gestionnaire_session.get_or_create_session(session_id, "creator")

    assert session["seed_data"] == {}


def test_session_suppression(gestionnaire_session):
    """delete_session doit supprimer la session de la mémoire."""
    session_id = str(uuid.uuid4())
    gestionnaire_session.get_or_create_session(session_id, "merchant")

    # Vérification que la session existe
    assert gestionnaire_session.get_session(session_id) is not None

    # Suppression
    gestionnaire_session.delete_session(session_id)

    # Vérification que la session n'existe plus
    assert gestionnaire_session.get_session(session_id) is None
