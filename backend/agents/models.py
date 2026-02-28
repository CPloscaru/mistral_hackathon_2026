"""
Modèles Pydantic pour les réponses de l'agent et l'état de session.
"""
from pydantic import BaseModel


class AgentResponse(BaseModel):
    """Réponse structurée retournée par le swarm d'agents."""
    message: str
    components: list = []  # Vide jusqu'en Phase 3 (composants A2UI)


class SessionState(BaseModel):
    """État complet d'une session utilisateur en mémoire."""
    session_id: str
    persona: str  # "creator" | "freelance" | "merchant"
    seed_data: dict
    maturity_level: int = 1  # Niveau d'évolution de la persona (1-4)
    active_widgets: list = []  # Composants UI actifs dans la session
