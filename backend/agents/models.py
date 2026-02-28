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


class AdminChecklistItem(BaseModel):
    """Item de la checklist administrative (pré-requis auto-entreprise, etc.)."""
    label: str              # "S'inscrire sur le guichet unique INPI"
    description: str        # Explication courte
    url: str | None = None  # Lien officiel (ex: https://procedures.inpi.fr)
    done: bool = False


class CalendarEvent(BaseModel):
    """Événement du calendrier lié au plan SMART."""
    date: str               # "2026-03-07" ou "2026-03-W2" (semaine)
    titre: str              # "Relancer Client X"
    description: str
    type: str               # "action" | "rappel" | "deadline"


class ToolsData(BaseModel):
    """Données peuplées par le Swarm pour les outils U2AI."""
    admin_checklist: list[AdminChecklistItem] = []
    calendar_events: list[CalendarEvent] = []


class OnboardingPlan(BaseModel):
    """Plan SMART structuré produit par le Swarm onboarding."""
    synthese_profil: str          # Résumé du profil
    objectif_smart: str           # L'objectif SMART (phrase clé)
    phases: list[PlanPhase]       # Les 3 phases du plan
    prochaines_etapes: list[str]  # Les 3 étapes immédiates
    tools_data: ToolsData | None = None  # Données pour les outils dashboard


class SessionState(BaseModel):
    """État complet d'une session utilisateur en mémoire."""
    session_id: str
    persona: str  # "creator" | "merchant"
    seed_data: dict
    maturity_level: int = 1  # Niveau d'évolution de la persona (1-4)
    active_widgets: list = []  # Composants UI actifs dans la session
