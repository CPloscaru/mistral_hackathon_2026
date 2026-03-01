"""
Endpoint POST /chat/stream — streaming conversationnel.

Branche entre :
- Onboarding agent (maturity_level < 2) : collecte du profil
- Orchestrateur (maturity_level >= 2) : assistant multi-agent post-onboarding
"""
import json
import logging
import uuid

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.routes.chat_common import ChatRequest
from backend.routes.chat_init import _stream_onboarding_agent
from backend.session.manager import session_manager
from backend.session import db
from backend.agents.orchestrator import get_or_create_orchestrator
from backend.agents.specialist_juridique import get_or_create_specialist_juridique
from backend.tools.interaction import get_and_clear_interaction_events

logger = logging.getLogger("kameleon.chat_stream")

router = APIRouter()


async def _stream_orchestrator(session: dict, message: str, chat_type: str = "main"):
    """
    Stream les tokens de l'orchestrateur via Server-Sent Events.
    Gère aussi les événements interaction (propose_choices).
    """
    session_id = session["session_id"]
    agent = get_or_create_orchestrator(session_id, session)

    # Sauvegarder le message utilisateur
    db.save_message(session_id, "user", message, chat_type=chat_type)

    # Vider les événements résiduels avant de commencer
    get_and_clear_interaction_events()

    full_text = ""
    event_count = 0

    logger.info("=== ORCHESTRATOR STREAM START === session=%s, message='%s'", session_id, message[:100])

    try:
        async for event in agent.stream_async(message):
            event_count += 1
            event_keys = list(event.keys()) if isinstance(event, dict) else str(type(event))

            # Log tous les 10 events, events spéciaux, ou tool events
            is_tool_event = any(k in event for k in ("current_tool_use", "tool_result")) if isinstance(event, dict) else False
            if event_count <= 5 or event_count % 20 == 0 or "result" in event or is_tool_event:
                extra = ""
                if is_tool_event and "current_tool_use" in event:
                    tool_info = event["current_tool_use"]
                    extra = f" tool={tool_info.get('name', '?')}"
                logger.info(
                    "Stream event #%d — keys=%s%s",
                    event_count, event_keys, extra,
                )

            # Texte de l'orchestrateur
            if "data" in event:
                chunk = event["data"]
                if not isinstance(chunk, str):
                    logger.warning(
                        "Stream event #%d — data is NOT str, type=%s, value=%s",
                        event_count, type(chunk).__name__, repr(chunk)[:200],
                    )
                    chunk = str(chunk) if chunk else ""
                full_text += chunk
                yield {"data": chunk, "event": "token"}

            # Après chaque event, vérifier si un tool a produit des interaction events
            for ie in get_and_clear_interaction_events():
                logger.info("Emitting interaction event: %s", ie.get("question", "?"))
                yield {
                    "data": json.dumps(ie, ensure_ascii=False),
                    "event": "interaction",
                }

            # Résultat final
            if "result" in event:
                logger.info(
                    "=== ORCHESTRATOR STREAM RESULT === events_total=%d, text_len=%d",
                    event_count, len(full_text),
                )
                # Dernière vérification des interaction events
                for ie in get_and_clear_interaction_events():
                    logger.info("Emitting final interaction event: %s", ie.get("question", "?"))
                    yield {
                        "data": json.dumps(ie, ensure_ascii=False),
                        "event": "interaction",
                    }

                # Sauvegarder la réponse assistant
                clean_text = full_text.strip()
                if clean_text:
                    db.save_message(session_id, "assistant", clean_text, chat_type=chat_type)

                yield {
                    "data": json.dumps({"done": True}, ensure_ascii=False),
                    "event": "done",
                }

    except Exception as exc:
        logger.exception(
            "=== ORCHESTRATOR STREAM ERROR === session=%s, events_so_far=%d, error_type=%s, error=%s",
            session_id, event_count, type(exc).__name__, str(exc)[:500],
        )
        yield {
            "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            "event": "error",
        }


async def _stream_specialist(session: dict, message: str, chat_type: str):
    """
    Stream les tokens d'un agent spécialiste (ex: juridique) via SSE.
    Même pattern que l'orchestrateur mais avec un agent dédié.
    """
    session_id = session["session_id"]

    # Routing vers le bon spécialiste selon le chat_type
    if chat_type == "specialist_juridique":
        agent = get_or_create_specialist_juridique(session_id, session)
    else:
        logger.error("Unknown specialist chat_type: %s", chat_type)
        yield {"data": json.dumps({"error": f"Spécialiste inconnu : {chat_type}"}), "event": "error"}
        return

    db.save_message(session_id, "user", message, chat_type=chat_type)
    get_and_clear_interaction_events()

    full_text = ""

    try:
        async for event in agent.stream_async(message):
            if "data" in event:
                chunk = event["data"]
                full_text += chunk
                yield {"data": chunk, "event": "token"}

            if "result" in event:
                clean_text = full_text.strip()
                if clean_text:
                    db.save_message(session_id, "assistant", clean_text, chat_type=chat_type)
                yield {"data": json.dumps({"done": True}, ensure_ascii=False), "event": "done"}

    except Exception as exc:
        logger.exception("Specialist streaming error for session %s", session_id)
        yield {"data": json.dumps({"error": str(exc)}, ensure_ascii=False), "event": "error"}


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    """
    Stream les tokens d'une réponse d'agent via Server-Sent Events.
    Route vers l'onboarding, l'orchestrateur ou un spécialiste selon le contexte.
    """
    session_id = body.session_id or str(uuid.uuid4())
    session = session_manager.get_or_create_session(session_id)

    # Chat spécialiste dédié (ex: specialist_juridique)
    if body.chat_type and body.chat_type.startswith("specialist_"):
        return EventSourceResponse(_stream_specialist(session, body.message, chat_type=body.chat_type))

    # Post-onboarding : orchestrateur
    if session.get("maturity_level", 1) >= 2:
        return EventSourceResponse(_stream_orchestrator(session, body.message, chat_type=body.chat_type))

    # Onboarding : agent conversationnel
    return EventSourceResponse(_stream_onboarding_agent(session, body.message, chat_type=body.chat_type))
