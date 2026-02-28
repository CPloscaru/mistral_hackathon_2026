"""
Endpoints SSE de streaming pour Kameleon.

POST /chat/stream — stream les tokens d'une réponse d'agent via Server-Sent Events.
GET  /chat/init  — déclenche le message d'accueil de l'agent pour l'onboarding Sophie.

Supporte deux modes :
- Mode Agent (onboarding conversationnel) : événements {data, result}
- Mode Swarm (day-to-day) : événements {multiagent_node_stream, multiagent_result}
"""
import json
import re

from strands import Agent
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from backend.routes.chat import ChatRequest
from backend.session.manager import session_manager

# Sentinels
READY_SENTINEL = "[READY_FOR_PLAN]"
ONBOARDING_SENTINEL = "[ONBOARDING_COMPLETE]"

router = APIRouter()


def _extract_profile_json(text: str) -> dict | None:
    """Extrait le JSON de profil entre balises <profile_json> et </profile_json>."""
    match = re.search(r"<profile_json>\s*(\{.*?\})\s*</profile_json>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


async def _stream_swarm(swarm, message: str, session: dict):
    """
    Streame les événements d'un Swarm (format multiagent).

    Détecte [ONBOARDING_COMPLETE] pour émettre maturity_update.
    """
    session_id = session["session_id"]

    async for event in swarm.stream_async(message):
        event_type = event.get("type")

        if event_type == "multiagent_node_stream":
            inner = event.get("event", {})
            raw_data = inner.get("data", "")

            if not raw_data or not raw_data.strip():
                continue

            if ONBOARDING_SENTINEL in raw_data:
                clean_text = raw_data.replace(ONBOARDING_SENTINEL, "").strip()

                current_level = session["maturity_level"]
                new_level = current_level + 1
                session_manager.update_session_state(
                    session_id=session_id,
                    maturity_level=new_level,
                )

                if clean_text:
                    yield {"data": clean_text, "event": "token"}

                yield {
                    "data": json.dumps({"level": new_level}, ensure_ascii=False),
                    "event": "maturity_update",
                }
            else:
                yield {"data": raw_data, "event": "token"}

        elif event_type == "multiagent_result":
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


async def _event_generator(session: dict, message: str):
    """
    Générateur d'événements SSE pour une session donnée.

    Détecte automatiquement le mode (Agent vs Swarm) et adapte le streaming.

    Événements émis :
    - event: token       — fragment de texte généré par l'agent
    - event: maturity_update — transition de maturité détectée
    - event: done        — fin du flux, inclut active_widgets
    - event: error       — erreur durant le streaming
    """
    agent_or_swarm = session["agent"]
    session_id = session["session_id"]
    is_agent = isinstance(agent_or_swarm, Agent)

    try:
        if not is_agent:
            # Mode Swarm (day-to-day) — délègue à _stream_swarm
            async for sse_event in _stream_swarm(agent_or_swarm, message, session):
                yield sse_event
            return

        # Mode Agent (onboarding conversationnel)
        # Buffer pour éviter que le sentinel leak dans le stream token par token
        full_text = ""
        buffer = ""
        sentinel_found = False

        async for event in agent_or_swarm.stream_async(message):
            if "data" in event:
                chunk = event["data"]
                full_text += chunk

                # Après le sentinel, on accumule sans streamer (profile_json etc.)
                if sentinel_found:
                    continue

                buffer += chunk

                # Si le buffer contient le sentinel complet → stop streaming
                if READY_SENTINEL in buffer:
                    before = buffer.split(READY_SENTINEL)[0]
                    if before.strip():
                        yield {"data": before, "event": "token"}
                    sentinel_found = True
                    continue

                # Le sentinel commence par "[" — buffer dès qu'on en voit un
                if "[" in buffer:
                    bracket_pos = buffer.index("[")
                    tail = buffer[bracket_pos:]
                    if READY_SENTINEL.startswith(tail):
                        safe = buffer[:bracket_pos]
                        if safe:
                            yield {"data": safe, "event": "token"}
                        buffer = tail
                        continue
                    yield {"data": buffer, "event": "token"}
                    buffer = ""
                else:
                    yield {"data": buffer, "event": "token"}
                    buffer = ""

            elif "result" in event:
                if READY_SENTINEL in full_text:
                    # Extraire le JSON de profil
                    profile_json = _extract_profile_json(full_text)

                    # Sauvegarder le profil dans la session
                    if profile_json:
                        session_manager.update_session_state(
                            session_id=session_id,
                            onboarding_data=profile_json,
                        )

                    # Émettre l'événement ready_for_plan (le Swarm sera lancé séparément)
                    yield {
                        "data": json.dumps(
                            {"profile": profile_json or {}},
                            ensure_ascii=False,
                        ),
                        "event": "ready_for_plan",
                    }
                else:
                    # Pas de sentinel — conversation normale, done
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
