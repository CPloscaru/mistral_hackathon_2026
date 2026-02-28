"""
Factory pour créer un Swarm Strands par session utilisateur.
Chaque session reçoit sa propre instance de Swarm avec le ton de persona baked-in.
"""
from strands import Agent
from strands.models.mistral import MistralModel
from strands.multiagent import Swarm
from strands.agent.conversation_manager import SlidingWindowConversationManager

from backend.config import (
    MISTRAL_API,
    COORDINATOR_MODEL,
    MODEL_8B,
    MODEL_3B,
    MODEL_14B,
)
from backend.agents.prompts import build_system_prompt, build_coordinator_prompt


def create_swarm(persona: str, seed_data: dict) -> Swarm:
    """
    Construit un Swarm Strands complet pour une session utilisateur.

    Crée 6 agents indépendants (1 coordinateur + 5 fonctionnels) avec :
    - Le modèle Mistral approprié à chaque fonction
    - Le prompt système personnalisé au ton de la persona
    - Les données de seed injectées dans le contexte
    - Un SlidingWindowConversationManager dédié par agent

    Args:
        persona: Type de persona ("creator", "freelance", "merchant")
        seed_data: Données de seed de l'utilisateur (peut être vide pour Sophie)

    Returns:
        Swarm configuré avec le coordinateur comme entry_point
    """
    # Coordinator — Mistral Large pour le routage intelligent
    coordinator = Agent(
        name="coordinator",
        model=MistralModel(
            model_id=COORDINATOR_MODEL,
            api_key=MISTRAL_API,
        ),
        system_prompt=build_coordinator_prompt(persona, seed_data),
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    # Agent Clients — Ministral 8B pour la gestion des relations
    clients = Agent(
        name="clients",
        model=MistralModel(
            model_id=MODEL_8B,
            api_key=MISTRAL_API,
        ),
        system_prompt=build_system_prompt("clients", persona, seed_data),
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    # Agent Finances — Ministral 8B pour la comptabilité
    finances = Agent(
        name="finances",
        model=MistralModel(
            model_id=MODEL_8B,
            api_key=MISTRAL_API,
        ),
        system_prompt=build_system_prompt("finances", persona, seed_data),
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    # Agent Planning — Ministral 3B pour l'organisation du temps
    planning = Agent(
        name="planning",
        model=MistralModel(
            model_id=MODEL_3B,
            api_key=MISTRAL_API,
        ),
        system_prompt=build_system_prompt("planning", persona, seed_data),
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    # Agent Création — Ministral 14B pour la génération de contenu
    creation = Agent(
        name="creation",
        model=MistralModel(
            model_id=MODEL_14B,
            api_key=MISTRAL_API,
        ),
        system_prompt=build_system_prompt("creation", persona, seed_data),
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    # Agent Activité — Ministral 8B pour le suivi opérationnel
    activite = Agent(
        name="activite",
        model=MistralModel(
            model_id=MODEL_8B,
            api_key=MISTRAL_API,
        ),
        system_prompt=build_system_prompt("activite", persona, seed_data),
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    # Assemblage du Swarm avec le coordinateur comme point d'entrée
    swarm = Swarm(
        [coordinator, clients, finances, planning, creation, activite],
        entry_point=coordinator,
        max_handoffs=10,
        execution_timeout=120.0,
    )

    return swarm
