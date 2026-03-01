"""
Endpoint GET /chat/init — message d'accueil de l'agent pour l'onboarding.
"""
import json
import re
import uuid

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.session.manager import session_manager
from backend.session import db
from backend.agents.onboarding_chat import get_or_create_onboarding_agent

READY_SENTINEL = "[READY_FOR_PLAN]"

router = APIRouter()


async def _stream_onboarding_agent(session: dict, message: str, chat_type: str = "main"):
    """
    Stream les tokens de l'agent conversationnel d'onboarding.
    Détecte [READY_FOR_PLAN] pour signaler la fin de l'onboarding.
    """
    session_id = session["session_id"]
    agent = get_or_create_onboarding_agent(session_id)

    if message not in ("__INIT__",):
        db.save_message(session_id, "user", message, chat_type=chat_type)

    full_text = ""
    buffer = ""
    sentinel_found = False

    try:
        async for event in agent.stream_async(message):
            if "data" in event:
                chunk = event["data"]
                full_text += chunk

                if sentinel_found:
                    continue

                buffer += chunk

                if READY_SENTINEL in buffer:
                    before = buffer.split(READY_SENTINEL)[0]
                    if before.strip():
                        yield {"data": before, "event": "token"}
                    sentinel_found = True
                    continue

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
                clean_assistant = full_text.split(READY_SENTINEL)[0].strip()
                clean_assistant = re.sub(
                    r"<profile_json>.*?</profile_json>", "", clean_assistant, flags=re.DOTALL
                ).strip()
                if clean_assistant:
                    db.save_message(session_id, "assistant", clean_assistant, chat_type=chat_type)

                if READY_SENTINEL in full_text:
                    profile_json = _extract_profile_json(full_text)

                    if profile_json:
                        # Si l'utilisateur a mentionné un statut juridique précis, l'enregistrer
                        statut_from_profile = _detect_statut_juridique(profile_json)
                        session_manager.update_session_state(
                            session_id=session_id,
                            onboarding_data=profile_json,
                            statut_juridique=statut_from_profile,
                        )

                    yield {
                        "data": json.dumps(
                            {"profile": profile_json or {}},
                            ensure_ascii=False,
                        ),
                        "event": "ready_for_plan",
                    }
                else:
                    yield {
                        "data": json.dumps({"done": True}, ensure_ascii=False),
                        "event": "done",
                    }

    except Exception as exc:
        yield {
            "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            "event": "error",
        }


def _extract_profile_json(text: str) -> dict | None:
    """Extrait le JSON de profil entre balises <profile_json>."""
    match = re.search(r"<profile_json>\s*(\{.*?\})\s*</profile_json>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


# Statuts juridiques : (regex pattern, valeur normalisée)
# Ordonnés du plus spécifique au plus générique pour éviter les faux positifs
_STATUTS_PATTERNS: list[tuple[str, str]] = [
    (r"micro[- ]?entreprise", "micro-entreprise"),
    (r"auto[- ]?entrepreneur", "micro-entreprise"),
    (r"portage salarial", "portage salarial"),
    (r"entreprise individuelle", "EI"),
    (r"\bsasu\b", "SASU"),
    (r"\beurl\b", "EURL"),
    (r"\beirl\b", "EIRL"),
    (r"\bsarl\b", "SARL"),
    (r"\bsas\b", "SAS"),
    (r"\bei\b", "EI"),
    (r"\bsa\b", "SA"),
]


def _detect_statut_juridique(profile: dict) -> str | None:
    """
    Détecte un statut juridique précis dans le profil d'onboarding.
    Cherche dans statut_administratif en priorité, puis statut_souhaite.
    Retourne None si le statut est vague ("rien encore", "ne sait pas", etc.).
    """
    for field in ("statut_administratif", "statut_souhaite"):
        value = profile.get(field, "")
        if not value:
            continue
        value_lower = value.lower().strip()
        # Ignorer les valeurs clairement vagues
        if any(kw in value_lower for kw in ("rien", "aucun", "ne sai", "pas encore", "non renseigné", "pas défini", "hésite")):
            continue
        for pattern, normalized in _STATUTS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return normalized
    return None


@router.get("/chat/init")
async def chat_init(session_id: str):
    """
    Déclenche le message d'accueil de l'agent pour l'onboarding.
    Le message synthétique "__INIT__" est envoyé au coordinateur.
    """
    session = session_manager.get_or_create_session(session_id)
    return EventSourceResponse(_stream_onboarding_agent(session, "__INIT__", chat_type="main"))
