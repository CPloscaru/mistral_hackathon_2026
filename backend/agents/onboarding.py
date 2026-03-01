"""
Factory pour l'onboarding Kameleon — architecture en 2 phases.

Phase 1 : Agent conversationnel (Mistral Large) — guide la conversation,
           collecte les infos, maintient l'historique entre les tours.
Phase 2 : Swarm one-shot (profiler + recherche + expert_fr) — lancé une seule fois
           quand l'Agent a collecté assez d'infos, produit le plan final.
"""
import logging

from strands import Agent, tool
from strands.models.mistral import MistralModel
from strands.multiagent import Swarm
from strands.agent.conversation_manager import SlidingWindowConversationManager

logger = logging.getLogger("kameleon.swarm")

from backend.config import (
    MISTRAL_API,
    COORDINATOR_MODEL,
    MODEL_8B,
    MODEL_14B,
)
from backend.agents.prompts import (
    ONBOARDING_CONVERSATION_PROMPT,
    ONBOARDING_COORDINATOR_SWARM_PROMPT,
    ONBOARDING_PROFILER_PROMPT,
    ONBOARDING_RECHERCHE_PROMPT,
    ONBOARDING_EXPERT_FR_PROMPT,
)
from backend.tools.web_search import web_search
from backend.tools.ui_components import manage_ui_component


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


def _swarm_debug_callback(**kwargs):
    """Callback de debug pour les agents du Swarm — log seulement les événements importants."""
    if kwargs.get("force_stop", False):
        logger.warning("🛑 FORCE-STOPPED: %s", kwargs.get("force_stop_reason", "unknown"))
    elif "result" in kwargs:
        logger.info("✅ Agent completed")
    elif kwargs.get("complete", False):
        logger.info("📦 Generation complete")

    if "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
        logger.info("🔧 Tool: %s", kwargs["current_tool_use"]["name"])


def create_onboarding_swarm() -> Swarm:
    """
    Swarm onboarding avec coordinator (Mistral Large) comme cerveau.

    Architecture :
    - Coordinator (Mistral Large) : entry point, analyse le profil, appelle
      ask_recherche / ask_expert_fr (agents éphémères via tool closures),
      synthétise puis handoff vers profiler.
    - Profiler (14B) : reçoit profil + synthèse, produit le plan JSON SMART,
      active les composants UI, émet [ONBOARDING_COMPLETE].

    Les agents recherche et expert_fr sont créés à la volée dans les tools,
    ils ne font PAS partie du Swarm.
    """

    # --- Tools éphémères (closures capturant MISTRAL_API) ---

    @tool
    def ask_recherche(question: str) -> str:
        """Recherche web d'infos à jour pour un entrepreneur français.
        Args:
            question: Question précise de recherche, en français.
        """
        agent = Agent(
            model=MistralModel(model_id=MODEL_14B, api_key=MISTRAL_API, max_tokens=4096),
            system_prompt=ONBOARDING_RECHERCHE_PROMPT,
            tools=[web_search],
            callback_handler=_swarm_debug_callback,
        )
        result = agent(question)
        return str(result)

    @tool
    def ask_expert_fr(question: str) -> str:
        """Consulte la base de connaissances entrepreneuriat français.
        Args:
            question: Question sur statuts, URSSAF, ACRE, obligations.
        """
        agent = Agent(
            model=MistralModel(model_id=MODEL_8B, api_key=MISTRAL_API, max_tokens=4096),
            system_prompt=ONBOARDING_EXPERT_FR_PROMPT,
            callback_handler=_swarm_debug_callback,
        )
        result = agent(question)
        return str(result)

    # --- Swarm : coordinator + profiler ---

    coordinator = Agent(
        name="coordinator",
        description="Analyse le profil utilisateur et coordonne la recherche",
        model=MistralModel(model_id=COORDINATOR_MODEL, api_key=MISTRAL_API, max_tokens=8192),
        system_prompt=ONBOARDING_COORDINATOR_SWARM_PROMPT,
        tools=[ask_recherche, ask_expert_fr],
        callback_handler=_swarm_debug_callback,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    profiler = Agent(
        name="profiler",
        description="Produit le plan JSON structuré avec objectif SMART et active les composants UI",
        model=MistralModel(model_id=MODEL_14B, api_key=MISTRAL_API, max_tokens=8192),
        system_prompt=ONBOARDING_PROFILER_PROMPT,
        tools=[manage_ui_component],
        callback_handler=_swarm_debug_callback,
        conversation_manager=SlidingWindowConversationManager(window_size=40),
    )

    return Swarm(
        [coordinator, profiler],
        entry_point=coordinator,
        max_handoffs=10,
        execution_timeout=120.0,
    )
