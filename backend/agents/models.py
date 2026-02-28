"""
Modèles Pydantic pour les réponses de l'agent et l'état de session.
"""
from pydantic import BaseModel


class AgentResponse(BaseModel):
    """Réponse structurée retournée par le swarm d'agents."""
    message: str
    components: list = []  # Vide jusqu'en Phase 3 (composants A2UI)


class PlanPhase(BaseModel):
    """Une phase du plan d'action onboarding."""
    titre: str        # "Semaine 1", "Semaines 2-3", etc.
    objectif: str     # Objectif de la phase
    actions: list[str] # Actions concrètes


class OnboardingPlan(BaseModel):
    """Plan SMART structuré produit par le Swarm onboarding."""
    synthese_profil: str          # Résumé du profil
    objectif_smart: str           # L'objectif SMART (phrase clé)
    phases: list[PlanPhase]       # Les 3 phases du plan
    prochaines_etapes: list[str]  # Les 3 étapes immédiates


class SessionState(BaseModel):
    """État complet d'une session utilisateur en mémoire."""
    session_id: str
    persona: str  # "creator" | "merchant"
    seed_data: dict
    maturity_level: int = 1  # Niveau d'évolution de la persona (1-4)
    active_widgets: list = []  # Composants UI actifs dans la session
