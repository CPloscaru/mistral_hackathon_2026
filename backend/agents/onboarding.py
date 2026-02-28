"""
Factory pour le Swarm d'onboarding Kameleon.

Swarm dédié à l'accompagnement des nouveaux utilisateurs (Sophie/creator).
4 agents : coordinateur (mène la conversation), profiler (analyse + plan),
recherche (web search Brave), expert FR (base de connaissances entrepreneuriat).
"""
from strands import Agent
from strands.models.mistral import MistralModel
from strands.multiagent import Swarm
from strands.agent.conversation_manager import SlidingWindowConversationManager

from backend.config import (
    MISTRAL_API,
    COORDINATOR_MODEL,
    MODEL_8B,
    MODEL_14B,
)
from backend.agents.prompts import (
    ONBOARDING_COORDINATOR_PROMPT,
    ONBOARDING_PROFILER_PROMPT,
    ONBOARDING_RECHERCHE_PROMPT,
    ONBOARDING_EXPERT_FR_PROMPT,
)
from backend.tools.web_search import web_search


def create_onboarding_swarm() -> Swarm:
    """
    Construit le Swarm d'onboarding pour les nouveaux utilisateurs.

    Architecture :
    - Coordinator (Mistral Large) : mène la conversation, collecte les infos, orchestre
    - Profiler (8B) : analyse le profil et produit un plan d'action personnalisé
    - Recherche (14B + web_search tool) : recherche web temps réel via Brave Search
    - Expert FR (8B) : base de connaissances entrepreneuriat français intégrée au prompt

    Returns:
        Swarm configuré avec le coordinateur comme entry_point
    """
    coordinator = Agent(
        name="coordinator",
        model=MistralModel(
            model_id=COORDINATOR_MODEL,
            api_key=MISTRAL_API,
        ),
        system_prompt=ONBOARDING_COORDINATOR_PROMPT,
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    profiler = Agent(
        name="profiler",
        model=MistralModel(
            model_id=MODEL_8B,
            api_key=MISTRAL_API,
        ),
        system_prompt=ONBOARDING_PROFILER_PROMPT,
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    recherche = Agent(
        name="recherche",
        model=MistralModel(
            model_id=MODEL_14B,
            api_key=MISTRAL_API,
        ),
        system_prompt=ONBOARDING_RECHERCHE_PROMPT,
        tools=[web_search],
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    expert_fr = Agent(
        name="expert_fr",
        model=MistralModel(
            model_id=MODEL_8B,
            api_key=MISTRAL_API,
        ),
        system_prompt=ONBOARDING_EXPERT_FR_PROMPT,
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    swarm = Swarm(
        [coordinator, profiler, recherche, expert_fr],
        entry_point=coordinator,
        max_handoffs=10,
        execution_timeout=120.0,
    )

    return swarm
