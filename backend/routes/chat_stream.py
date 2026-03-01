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
from backend.session import db

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


def _extract_plan_json(text: str) -> dict | None:
    """
    Extrait le JSON de plan structuré.
    Tente d'abord <plan_json>...</plan_json>, puis ```json...```, puis un JSON brut.
    """
    # 1. Balises <plan_json>
    match = re.search(r"<plan_json>\s*(\{.*\})\s*</plan_json>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. Bloc markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. JSON brut — compteur d'accolades pour trouver le premier objet complet
    start = 0
    while True:
        idx = text.find("{", start)
        if idx == -1:
            break
        depth = 0
        in_string = False
        escape = False
        for i in range(idx, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[idx:i + 1])
                        if isinstance(data, dict) and ("objectif_smart" in data or "phases" in data):
                            return data
                    except json.JSONDecodeError:
                        pass
                    break
        start = idx + 1

    return None


async def _stream_swarm(swarm, message: str, session: dict):
    """
    Streame les événements d'un Swarm (format multiagent).

    Détecte [ONBOARDING_COMPLETE] pour émettre maturity_update.
    Extrait <plan_json> pour émettre plan_ready (au lieu de streamer le texte brut).
    """
    import logging
    logger = logging.getLogger("kameleon.swarm")

    session_id = session["session_id"]
    token_count = 0
    agent_trace = []  # trace ordered list of agent activations
    ui_events = []  # A2UI — accumulateur partagé via invocation_state

    full_text = ""
    current_node = None  # track which agent is currently streaming
    profiler_text = ""   # only profiler output (for clean persistence)

    async for event in swarm.stream_async(
        message,
        invocation_state={
            "session_id": session_id,
            "ui_events": ui_events,
        },
    ):
        event_type = event.get("type")

        if event_type == "multiagent_node_start":
            node_id = event.get("node_id", "?")
            current_node = node_id
            agent_trace.append(node_id)
            logger.info("▶️ [TRACE] Agent démarré: %s (trace: %s)", node_id, " → ".join(agent_trace))

        elif event_type == "multiagent_handoff":
            from_nodes = event.get("from_node_ids", [])
            to_nodes = event.get("to_node_ids", [])
            msg = event.get("message", "")
            logger.info("🔀 [HANDOFF] %s → %s | message: %s",
                        ", ".join(from_nodes) if from_nodes else "?",
                        ", ".join(to_nodes) if to_nodes else "?",
                        msg[:100] if msg else "non spécifié")

        elif event_type == "multiagent_node_stop":
            node_id = event.get("node_id", "?")
            logger.info("⏹️ [TRACE] Agent terminé: %s", node_id)

        elif event_type == "multiagent_node_stream":
            inner = event.get("event", {})
            raw_data = inner.get("data", "")

            if not raw_data or not raw_data.strip():
                continue

            token_count += 1
            full_text += raw_data
            if current_node == "profiler":
                profiler_text += raw_data

            is_day_to_day = session.get("maturity_level", 1) >= 2

            if is_day_to_day:
                # Day-to-day: stream tokens en temps réel
                yield {"data": raw_data, "event": "token"}
            else:
                # Onboarding: on attend le résultat complet pour extraire plan_json
                if token_count % 50 == 0:
                    yield {"data": json.dumps({"tokens": token_count}), "event": "progress"}

        elif event_type == "multiagent_result":
            has_sentinel = ONBOARDING_SENTINEL in full_text
            logger.info(
                "🗺️ [TRACE] Parcours complet: %s",
                " → ".join(agent_trace) if agent_trace else "aucun agent tracé",
            )
            logger.info(
                "📊 Swarm DONE — %d tokens, %d chars, sentinel=%s, last 100: ...%s",
                token_count, len(full_text), has_sentinel,
                full_text[-100:].replace("\n", "\\n"),
            )

            # Extraire le plan JSON structuré
            plan_data = _extract_plan_json(full_text)

            # Bump maturity si sentinel détecté OU plan produit (une seule fois : 1→2)
            current_level = session["maturity_level"]
            if (has_sentinel or plan_data) and current_level == 1:
                new_level = 2
                session_manager.update_session_state(
                    session_id=session_id,
                    maturity_level=new_level,
                )
                logger.info("Maturity bump %d→%d (sentinel=%s, plan=%s)", current_level, new_level, has_sentinel, bool(plan_data))

                yield {
                    "data": json.dumps({"level": new_level}, ensure_ascii=False),
                    "event": "maturity_update",
                }

                # Swap vers day-to-day swarm après le plan
                from backend.agents.factory import create_swarm
                day_to_day = create_swarm(session["persona"], session.get("seed_data", {}))
                session["agent"] = day_to_day
                logger.info("Swapped to day-to-day swarm after plan")

            # Persister la réponse (nettoyée — uniquement le texte du profiler en onboarding)
            is_onboarding = session.get("maturity_level", 1) < 2 or (has_sentinel or plan_data)
            persist_text = profiler_text if (is_onboarding and profiler_text) else full_text
            clean_full = persist_text.replace(ONBOARDING_SENTINEL, "").strip()
            clean_full = re.sub(
                r"<plan_json>.*?</plan_json>", "", clean_full, flags=re.DOTALL
            ).strip()
            if clean_full:
                db.save_message(session_id, "assistant", clean_full)

            # Émettre plan_ready avec le JSON structuré (ou fallback texte)
            if plan_data:
                # Persister aussi le plan structuré dans la session
                session_manager.update_session_state(
                    session_id=session_id,
                    plan_data=plan_data,
                )

                # Persister tools_data si présent
                tools_data = plan_data.get("tools_data")
                if tools_data:
                    if tools_data.get("admin_checklist"):
                        db.save_admin_checklist(session_id, tools_data["admin_checklist"])
                        logger.info("Persisted %d admin checklist items", len(tools_data["admin_checklist"]))
                    if tools_data.get("calendar_events"):
                        db.save_calendar_events(session_id, tools_data["calendar_events"])
                        logger.info("Persisted %d calendar events", len(tools_data["calendar_events"]))
                    if tools_data.get("budget_data"):
                        db.save_budget_data(session_id, tools_data["budget_data"])
                        logger.info("Persisted budget_data")

                yield {
                    "data": json.dumps(plan_data, ensure_ascii=False),
                    "event": "plan_ready",
                }

                # A2UI fallback — si l'agent n'a émis aucun ui_event, activation auto (3 composants seulement)
                if not ui_events:
                    logger.warning("A2UI fallback: agent n'a pas appelé manage_ui_component, activation auto")
                    fallback_components = [
                        {"action": "activate", "type": "admin", "id": "admin-1",
                         "title": "Checklist Administrative", "icon": "\U0001f4cb"},
                        {"action": "activate", "type": "crm", "id": "crm-1",
                         "title": "Clients & Facturation", "icon": "\U0001f4bc"},
                        {"action": "activate", "type": "roadmap", "id": "roadmap-1",
                         "title": "Roadmap du Plan", "icon": "\U0001f5fa\ufe0f",
                         "data": {"phases": plan_data.get("phases", []),
                                  "objectif_smart": plan_data.get("objectif_smart", "")}},
                    ]
                    ui_events.extend(fallback_components)

                # A2UI — émettre les ui_component events (agent ou fallback)
                for comp in ui_events:
                    yield {"data": json.dumps(comp, ensure_ascii=False), "event": "ui_component"}
                    logger.info("A2UI event: %s %s", comp.get("action"), comp.get("type"))

                # Calculer l'état final des active_components
                current_components = list(session.get("active_components", []))
                for evt in ui_events:
                    if evt["action"] == "activate":
                        current_components = [c for c in current_components if c["type"] != evt["type"]]
                        current_components.append(evt)
                    elif evt["action"] == "update":
                        for c in current_components:
                            if c["type"] == evt["type"]:
                                if evt.get("data"):
                                    c["data"] = evt["data"]
                                if evt.get("title"):
                                    c["title"] = evt["title"]
                                break
                    elif evt["action"] == "deactivate":
                        current_components = [c for c in current_components if c["type"] != evt["type"]]

                session_manager.update_session_state(
                    session_id=session_id,
                    active_components=current_components,
                )
            else:
                is_day_to_day = session.get("maturity_level", 1) >= 2
                if not is_day_to_day:
                    # Onboarding fallback: pas de JSON structuré, streamer le texte brut
                    logger.warning("Pas de <plan_json> trouvé, fallback texte brut")
                    if clean_full:
                        yield {"data": clean_full, "event": "token"}

                # Day-to-day: emit ui_component events if any
                if ui_events:
                    for comp in ui_events:
                        yield {"data": json.dumps(comp, ensure_ascii=False), "event": "ui_component"}
                        logger.info("A2UI event (day-to-day): %s %s", comp.get("action"), comp.get("type"))
                    # Persist active_components
                    current_components = list(session.get("active_components", []))
                    for evt in ui_events:
                        if evt["action"] == "activate":
                            current_components = [c for c in current_components if c["type"] != evt["type"]]
                            current_components.append(evt)
                        elif evt["action"] == "update":
                            for c in current_components:
                                if c["type"] == evt["type"]:
                                    if evt.get("data"):
                                        c["data"] = evt["data"]
                                    break
                        elif evt["action"] == "deactivate":
                            current_components = [c for c in current_components if c["type"] != evt["type"]]
                    session_manager.update_session_state(
                        session_id=session_id,
                        active_components=current_components,
                    )

            yield {
                "data": json.dumps(
                    {
                        "done": True,
                        "active_components": session.get("active_components", []),
                    },
                    ensure_ascii=False,
                ),
                "event": "done",
            }

        else:
            logger.info("❓ Swarm event non géré: type=%s keys=%s", event_type, list(event.keys()))

    logger.info(
        "🏁 _stream_swarm loop ended — %d tokens, %d chars, sentinel_found=%s",
        token_count, len(full_text), ONBOARDING_SENTINEL in full_text,
    )


async def _event_generator(session: dict, message: str):
    """
    Générateur d'événements SSE pour une session donnée.

    Détecte automatiquement le mode (Agent vs Swarm) et adapte le streaming.

    Événements émis :
    - event: token       — fragment de texte généré par l'agent
    - event: maturity_update — transition de maturité détectée
    - event: done        — fin du flux, inclut active_components
    - event: error       — erreur durant le streaming
    """
    agent_or_swarm = session["agent"]
    session_id = session["session_id"]
    is_agent = isinstance(agent_or_swarm, Agent)

    # Persister le message utilisateur (sauf messages synthétiques)
    if message not in ("__INIT__", "__PLAN__"):
        db.save_message(session_id, "user", message)

    try:
        # Swarm one-shot : si on a les données d'onboarding et encore un Agent
        if (
            is_agent
            and isinstance(session.get("onboarding_data"), dict)
            and session["onboarding_data"].get("prenom")
        ):
            if message == "__PLAN__":
                # Lancé depuis /personal-assistant → exécuter le Swarm
                session = session_manager.swap_to_swarm(session_id)
                swarm = session["agent"]
                from datetime import date
                profile_data = dict(session["onboarding_data"])
                profile_data["date_du_jour"] = date.today().isoformat()
                profile_json_str = json.dumps(profile_data, ensure_ascii=False)
                profile_msg = f"<profile_json>\n{profile_json_str}\n</profile_json>"
                async for sse_event in _stream_swarm(swarm, profile_msg, session):
                    yield sse_event
                return
            else:
                # Message utilisateur depuis / → redirect vers /personal-assistant
                yield {
                    "data": json.dumps(
                        {"profile": session.get("onboarding_data", {})},
                        ensure_ascii=False,
                    ),
                    "event": "plan_ready",
                }
                yield {
                    "data": json.dumps({"done": True}, ensure_ascii=False),
                    "event": "done",
                }
                return

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
                # Persister la réponse assistant (nettoyée des sentinels et balises)
                clean_assistant = full_text.split(READY_SENTINEL)[0].strip()
                # Retirer les balises <profile_json>...</profile_json>
                clean_assistant = re.sub(
                    r"<profile_json>.*?</profile_json>", "", clean_assistant, flags=re.DOTALL
                ).strip()
                if clean_assistant:
                    db.save_message(session_id, "assistant", clean_assistant)

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
                                "active_components": session.get("active_components", []),
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


@router.get("/chat/history")
async def chat_history(session_id: str):
    """
    Retourne l'historique des messages d'une session.

    Args:
        session_id: Identifiant de session (query param)

    Returns:
        Liste de messages {role, content, created_at}
    """
    messages = db.load_messages(session_id)
    return {"messages": messages}


@router.post("/chat/inject-onboarding")
async def inject_onboarding(request: Request, body: dict):
    """
    Endpoint de test : injecte onboarding_data dans la session en mémoire + SQLite.
    Permet au script 02_second_step_plan.py de déclencher le Swarm sans refaire l'onboarding.
    """
    session_id = body.get("session_id")
    profile = body.get("profile", {})

    session = session_manager.get_session(session_id)
    if session is None:
        return {"error": "Session introuvable"}

    session_manager.update_session_state(
        session_id=session_id,
        onboarding_data=profile,
    )
    return {"ok": True, "session_id": session_id}


@router.get("/chat/session-info")
async def session_info(request: Request, session_id: str):
    """
    Retourne les infos publiques de la session (prenom, assistant_name, persona).
    Utilisé par le frontend PersonalAssistant pour personnaliser l'interface.
    """
    record = db.load_session(session_id)
    if record is None:
        return {"error": "Session introuvable"}

    onboarding_data = record.get("onboarding_data") or {}
    plan_data = onboarding_data.pop("_plan", None)
    return {
        "prenom": onboarding_data.get("prenom"),
        "assistant_name": record.get("assistant_name"),
        "persona": record.get("persona"),
        "maturity_level": record.get("maturity_level"),
        "plan": plan_data,
        "active_components": record.get("active_components", []),
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
