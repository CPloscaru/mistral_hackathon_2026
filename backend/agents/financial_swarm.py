"""
Agent financier — calcul de prévisions financières.

Architecture : un seul agent (Magistral Medium) qui fait tout séquentiellement :
1. Web search pour les taux de cotisations
2. Récupère les factures via manage_crm
3. Calcule les prévisions
4. Sauvegarde via manage_previsions
"""
import logging
from pathlib import Path

from strands import Agent, tool

from backend.config import COORDINATOR_MODEL, make_model
from backend.tools.crm import manage_crm
from backend.tools.previsions import manage_previsions
from backend.tools.web_search import web_search

logger = logging.getLogger("kameleon.financial_agent")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "financial_calculateur.txt"
_CALCULATEUR_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


@tool
def financial_agent(session_id: str, objectif_net: float, statut_juridique: str) -> str:
    """Lance une analyse financière complète pour l'utilisateur.

    Calcule le CA brut nécessaire, analyse les factures existantes,
    recherche les taux de cotisations en ligne, et détermine le nombre
    de missions supplémentaires pour atteindre l'objectif.

    Args:
        session_id: ID de la session utilisateur
        objectif_net: Objectif de revenu net annuel avant impôt sur le revenu (en euros)
        statut_juridique: Statut juridique de l'utilisateur (ex: "micro-entreprise", "SASU", "EURL")
    """
    logger.info(
        "=== FINANCIAL AGENT CALLED === session=%s, objectif=%s€, statut=%s",
        session_id, objectif_net, statut_juridique,
    )

    try:
        calculateur_prompt = (_CALCULATEUR_PROMPT_TEMPLATE
                              .replace("{session_id}", session_id)
                              .replace("{objectif_net}", str(objectif_net))
                              .replace("{statut_juridique}", statut_juridique)
                              .replace("{prenom}", "l'utilisateur"))
    except Exception as exc:
        logger.exception("ERREUR construction prompt")
        return f"Erreur construction prompt : {exc}"

    try:
        agent = Agent(
            name="financial_calculateur",
            model=make_model(COORDINATOR_MODEL),
            system_prompt=calculateur_prompt,
            tools=[web_search, manage_crm, manage_previsions],
            callback_handler=None,
        )
    except Exception as exc:
        logger.exception("ERREUR création agent")
        return f"Erreur création agent : {exc}"

    user_message = (
        f"Calcule les prévisions financières pour un objectif net de {objectif_net}€ "
        f"avec le statut {statut_juridique}. "
        f"Le session_id est '{session_id}'."
    )
    logger.info("Lancement agent financier avec message: %s", user_message[:100])

    try:
        result = agent(user_message)
    except Exception as exc:
        logger.exception("=== FINANCIAL AGENT CRASHED === session=%s", session_id)
        return f"Erreur lors du calcul des prévisions : {exc}"

    # Extraire le texte
    try:
        text = result.message["content"][0]["text"]
        logger.info("=== FINANCIAL AGENT OK === text_len=%d", len(text))
        return text
    except (KeyError, IndexError, TypeError):
        logger.warning("Extraction texte fallback")
        return str(result)
