"""
Route POST /chat pour l'interface de conversation de Kameleon.
Reçoit un message utilisateur, exécute le swarm d'agents, retourne une AgentResponse.
"""
import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.agents.models import AgentResponse
from backend.session.manager import session_manager


class ChatRequest(BaseModel):
    """Corps de la requête POST /chat."""
    message: str
    session_id: str | None = None


router = APIRouter()


@router.post("/chat", response_model=AgentResponse)
async def chat(request: Request, body: ChatRequest):
    """
    Exécute une conversation avec le swarm d'agents Kameleon.

    - Résout la persona depuis request.state.persona (injecté par SubdomainMiddleware)
    - Crée ou récupère la session utilisateur
    - Exécute le swarm avec le message
    - Retourne la réponse de l'agent coordinateur

    Args:
        request: Requête FastAPI (contient request.state.persona)
        body: Corps JSON avec message et session_id optionnel

    Returns:
        AgentResponse avec le message de l'agent et les composants UI (vide pour l'instant)
    """
    persona = request.state.persona
    session_id = body.session_id or str(uuid.uuid4())

    session = session_manager.get_or_create_session(session_id, persona)
    swarm = session["swarm"]

    try:
        result = swarm(body.message)

        # Extraction du texte depuis le SwarmResult
        # Le résultat final provient du coordinateur (entry_point) ou du dernier agent
        text = _extract_text_from_result(result)

    except Exception as exc:
        text = f"Désolé, une erreur s'est produite : {exc}"

    return AgentResponse(message=text, components=[])


def _extract_text_from_result(result) -> str:
    """
    Extrait le texte lisible depuis un SwarmResult.

    Stratégie :
    1. Cherche le résultat du coordinateur dans results dict
    2. Parcourt les agent results pour trouver le dernier texte
    3. Fallback : str(result)

    Args:
        result: SwarmResult retourné par swarm(message)

    Returns:
        Texte de la réponse de l'agent
    """
    # Cherche d'abord le résultat du coordinateur
    if hasattr(result, "results") and result.results:
        # Essai direct sur le noeud "coordinator"
        coordinator_node = result.results.get("coordinator")
        if coordinator_node is not None:
            agent_results = coordinator_node.get_agent_results()
            if agent_results:
                return str(agent_results[-1]).strip()

        # Sinon, parcourt tous les noeuds dans l'ordre
        for node_result in result.results.values():
            agent_results = node_result.get_agent_results()
            if agent_results:
                last_text = str(agent_results[-1]).strip()
                if last_text:
                    return last_text

    # Fallback : conversion directe
    fallback = str(result).strip()
    return fallback if fallback else "Je n'ai pas pu générer de réponse."
