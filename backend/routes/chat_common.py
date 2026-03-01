"""
Modèles partagés et endpoints utilitaires pour le chat Kameleon.
"""
import json

from fastapi import APIRouter
from pydantic import BaseModel

from backend.session.manager import session_manager
from backend.session import db

router = APIRouter()


class ChatRequest(BaseModel):
    """Corps de la requête POST /chat/stream."""
    message: str
    session_id: str | None = None
    chat_type: str = "main"


@router.get("/session/active")
async def session_active():
    """Retourne le session_id de la dernière session active."""
    record = db.load_active_session()
    if record is None:
        return {"session_id": None}
    return {"session_id": record["session_id"]}


@router.get("/chat/history")
async def chat_history(session_id: str, chat_type: str | None = None):
    """Retourne l'historique des messages d'une session."""
    messages = db.load_messages(session_id, chat_type=chat_type)
    return {"messages": messages}


@router.get("/chat/session-info")
async def session_info(session_id: str):
    """
    Retourne les infos publiques de la session (prenom, assistant_name).
    Utilisé par le frontend PersonalAssistant pour personnaliser l'interface.
    """
    record = db.load_session(session_id)
    if record is None:
        return {"error": "Session introuvable"}

    onboarding_data = record.get("onboarding_data") or {}
    return {
        "prenom": onboarding_data.get("prenom"),
        "assistant_name": record.get("assistant_name"),
        "maturity_level": record.get("maturity_level"),
        "active_components": record.get("active_components", []),
    }
