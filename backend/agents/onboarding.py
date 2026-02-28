"""
Factory pour l'onboarding Kameleon — architecture en 2 phases.

Phase 1 : Agent conversationnel (Mistral Large) — guide la conversation,
           collecte les infos, maintient l'historique entre les tours.
Phase 2 : Swarm one-shot (profiler + recherche + expert_fr) — lancé une seule fois
           quand l'Agent a collecté assez d'infos, produit le plan final.
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
    ONBOARDING_CONVERSATION_PROMPT,
    ONBOARDING_PROFILER_PROMPT,
    ONBOARDING_RECHERCHE_PROMPT,
    ONBOARDING_EXPERT_FR_PROMPT,
)
from backend.tools.web_search import web_search


def create_onboarding_agent() -> Agent:
    """
    Agent conversationnel pour la collecte d'infos pendant l'onboarding.

    Utilise Mistral Large avec une fenêtre de conversation de 40 messages.
    Maintient l'historique entre les tours (pas de reset).
    Émet [READY_FOR_PLAN] + un résumé JSON quand il a assez d'infos.
    """
    return Agent(
        name="onboarding_coordinator",
        model=MistralModel(
            model_id=COORDINATOR_MODEL,
            api_key=MISTRAL_API,
        ),
        system_prompt=ONBOARDING_CONVERSATION_PROMPT,
        callback_handler=None,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )


def create_onboarding_swarm() -> Swarm:
    """
    Swarm one-shot pour le traitement final de l'onboarding.

    Architecture :
    - Profiler (8B) : entry point, analyse le profil JSON et produit un plan SMART
    - Recherche (14B + web_search) : recherche web temps réel via Brave Search
    - Expert FR (8B) : base de connaissances entrepreneuriat français

    Le profiler est l'entry point (pas de coordinator — la conversation est déjà faite).
    """
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
        [profiler, recherche, expert_fr],
        entry_point=profiler,
        max_handoffs=10,
        execution_timeout=120.0,
    )

    return swarm
