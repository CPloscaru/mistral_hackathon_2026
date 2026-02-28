"""
Tests de configuration du Swarm et du routage des agents.
Vérifie la structure du Swarm, les modèles assignés, et la configuration des agents.
Aucun appel réel à l'API Mistral — le client HTTP est mocké.
"""
import pytest
from unittest.mock import patch, MagicMock
from strands.agent.conversation_manager import SlidingWindowConversationManager

# Modèles attendus par agent (depuis backend/config.py)
MODELES_ATTENDUS = {
    "coordinator": "mistral-large-2512",
    "clients": "ministral-8b-2512",
    "finances": "ministral-8b-2512",
    "planning": "ministral-3b-2512",
    "creation": "ministral-14b-2512",
    "activite": "ministral-8b-2512",
}

# Noms attendus des 6 agents
NOMS_AGENTS_ATTENDUS = ["coordinator", "clients", "finances", "planning", "creation", "activite"]


@pytest.fixture(scope="module")
def swarm_merchant():
    """Retourne un Swarm configuré pour la persona merchant (client HTTP mocké)."""
    with patch("mistralai.Mistral") as mock_client:
        mock_client.return_value = MagicMock()
        from backend.agents.factory import create_swarm
        return create_swarm("merchant", {})


def test_coordinator_est_entry_point(swarm_merchant):
    """Le coordinateur doit être le point d'entrée du Swarm."""
    assert swarm_merchant.entry_point is not None
    assert swarm_merchant.entry_point.name == "coordinator"


def test_swarm_contient_6_agents(swarm_merchant):
    """Le Swarm doit contenir exactement 6 agents (1 coordinateur + 5 fonctionnels)."""
    assert len(swarm_merchant.nodes) == 6


def test_agents_ont_bons_modeles(swarm_merchant):
    """Chaque agent doit utiliser le modèle Mistral approprié à sa fonction."""
    for nom_agent, modele_attendu in MODELES_ATTENDUS.items():
        assert nom_agent in swarm_merchant.nodes, f"Agent '{nom_agent}' manquant dans le Swarm"
        agent = swarm_merchant.nodes[nom_agent].executor
        modele_reel = agent.model.get_config()["model_id"]
        assert modele_reel == modele_attendu, (
            f"Agent '{nom_agent}' : modèle attendu '{modele_attendu}', obtenu '{modele_reel}'"
        )


def test_conversation_manager_window_40(swarm_merchant):
    """Tous les agents doivent utiliser SlidingWindowConversationManager avec window_size=40."""
    for nom_agent, node in swarm_merchant.nodes.items():
        agent = node.executor
        cm = agent.conversation_manager
        assert isinstance(cm, SlidingWindowConversationManager), (
            f"Agent '{nom_agent}' n'utilise pas SlidingWindowConversationManager"
        )
        assert cm.window_size == 40, (
            f"Agent '{nom_agent}' : window_size attendu 40, obtenu {cm.window_size}"
        )


def test_callback_handler_none(swarm_merchant):
    """Tous les agents doivent utiliser null_callback_handler (pas PrintingCallbackHandler)."""
    for nom_agent, node in swarm_merchant.nodes.items():
        agent = node.executor
        cb = agent.callback_handler
        # Quand callback_handler=None est passé au constructeur, Strands utilise null_callback_handler
        assert hasattr(cb, "__name__"), f"Agent '{nom_agent}' : callback_handler sans attribut __name__"
        assert cb.__name__ == "null_callback_handler", (
            f"Agent '{nom_agent}' : callback_handler attendu 'null_callback_handler', obtenu '{cb.__name__}'"
        )


def test_tous_agents_nommes(swarm_merchant):
    """Tous les agents doivent avoir les noms corrects."""
    noms_reels = list(swarm_merchant.nodes.keys())
    for nom_attendu in NOMS_AGENTS_ATTENDUS:
        assert nom_attendu in noms_reels, f"Agent '{nom_attendu}' manquant dans le Swarm"
