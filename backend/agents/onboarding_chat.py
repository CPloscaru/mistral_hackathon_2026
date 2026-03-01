"""
Agent conversationnel d'onboarding — guide la conversation et collecte les infos.
Un agent par session, maintenu en mémoire pour garder l'historique.
"""
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

from backend.config import MISTRAL_LARGE, make_model
from backend.agents.prompts import ONBOARDING_CONVERSATION_PROMPT

# Cache des agents par session_id
_agents: dict[str, Agent] = {}


def get_or_create_onboarding_agent(session_id: str) -> Agent:
    """
    Retourne l'agent conversationnel d'onboarding pour cette session.
    Crée l'agent au premier appel, le réutilise ensuite (historique conservé).
    """
    if session_id not in _agents:
        _agents[session_id] = Agent(
            name="onboarding_coordinator",
            model=make_model(MISTRAL_LARGE),
            system_prompt=ONBOARDING_CONVERSATION_PROMPT,
            callback_handler=None,
            conversation_manager=SlidingWindowConversationManager(window_size=40),
        )
    return _agents[session_id]


def remove_onboarding_agent(session_id: str) -> None:
    """Libère l'agent conversationnel après l'onboarding."""
    _agents.pop(session_id, None)
