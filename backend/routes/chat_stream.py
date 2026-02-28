"""
Endpoints SSE de streaming pour Kameleon.

POST /chat/stream — stream les tokens d'une réponse d'agent via Server-Sent Events.
GET  /chat/init  — déclenche le message d'accueil de l'agent pour l'onboarding Sophie.
"""
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from backend.routes.chat import ChatRequest
from backend.session.manager import session_manager

# Sentinel signalant la fin de l'onboarding
ONBOARDING_SENTINEL = "[ONBOARDING_COMPLETE]"

router = APIRouter()


async def _event_generator(session: dict, message: str):
    """
    Générateur d'événements SSE pour une session donnée.

    Événements émis :
    - event: token       — fragment de texte généré par l'agent
    - event: maturity_update — le sentinel [ONBOARDING_COMPLETE] a été détecté
    - event: done        — fin du flux, inclut active_widgets
    - event: error       — erreur durant le streaming

    Args:
        session: Dictionnaire de session (contient swarm, maturity_level, etc.)
        message: Message à envoyer au swarm
    """
    swarm = session["swarm"]
    session_id = session["session_id"]

    try:
        async for event in swarm.stream_async(message):
            event_type = event.get("type")

            if event_type == "multiagent_node_stream":
                inner = event.get("event", {})
                raw_data = inner.get("data", "")

                if not raw_data or not raw_data.strip():
                    # Filtre les tokens vides
                    continue

                if ONBOARDING_SENTINEL in raw_data:
                    # Retire le sentinel du texte visible
                    clean_text = raw_data.replace(ONBOARDING_SENTINEL, "").strip()

                    # Incrémente le niveau de maturité
                    current_level = session["maturity_level"]
                    new_level = current_level + 1
                    session_manager.update_session_state(
                        session_id=session_id,
                        maturity_level=new_level,
                    )

                    # Émet le token nettoyé (si non vide)
                    if clean_text:
                        yield {"data": clean_text, "event": "token"}

                    # Émet l'événement de transition de maturité
                    yield {
                        "data": json.dumps({"level": new_level}, ensure_ascii=False),
                        "event": "maturity_update",
                    }
                else:
                    yield {"data": raw_data, "event": "token"}

            elif event_type == "multiagent_result":
                # Fin du flux — émet le done avec les widgets actifs
                yield {
                    "data": json.dumps(
                        {
                            "done": True,
                            "active_widgets": session.get("active_widgets", []),
                        },
                        ensure_ascii=False,
                    ),
                    "event": "done",
                }

    except Exception as exc:
        yield {
            "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            "event": "error",
        }


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """
    Stream les tokens d'une réponse d'agent via Server-Sent Events.

    - Lit la persona depuis request.state.persona (injecté par SubdomainMiddleware)
    - Crée ou récupère la session
    - Stream les événements SSE : token, maturity_update, done, error

    Args:
        request: Requête FastAPI (contient request.state.persona)
        body: Corps JSON avec message et session_id optionnel

    Returns:
        EventSourceResponse (text/event-stream)
    """
    import uuid

    persona = request.state.persona
    session_id = body.session_id or str(uuid.uuid4())

    session = session_manager.get_or_create_session(session_id, persona)

    return EventSourceResponse(_event_generator(session, body.message))


@router.get("/chat/init")
async def chat_init(request: Request, session_id: str):
    """
    Déclenche le message d'accueil de l'agent pour l'onboarding.

    Utilisé par le frontend au chargement initial de la page pour Sophie.
    Pour les autres personas, retourne également un flux SSE (message de bienvenue standard).

    Le message synthétique "__INIT__" est envoyé au coordinateur, qui le traite
    sans déléguer aux agents spécialisés.

    Args:
        request: Requête FastAPI (contient request.state.persona)
        session_id: Identifiant de session passé en query param

    Returns:
        EventSourceResponse (text/event-stream)
    """
    persona = request.state.persona
    session = session_manager.get_or_create_session(session_id, persona)

    return EventSourceResponse(_event_generator(session, "__INIT__"))
