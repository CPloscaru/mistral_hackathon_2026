"""
Outil de gestion du statut juridique utilisateur.
Utilisable par le spécialiste juridique, l'orchestrateur et l'onboarding.
"""
import json
import logging

from strands import tool

from backend.session import db
from backend.session.manager import session_manager

logger = logging.getLogger("kameleon.tools.profil")


@tool
def manage_statut_juridique(session_id: str, action: str, statut: str = "") -> str:
    """Consulte ou met à jour le statut juridique de l'utilisateur.

    Actions disponibles :
    - "get" : retourne le statut juridique actuellement enregistré
    - "update" : enregistre un nouveau statut juridique (nécessite le paramètre statut)

    Utilise action="get" quand l'utilisateur demande quel est son statut juridique enregistré.
    Utilise action="update" quand l'utilisateur annonce clairement son choix de statut juridique
    (ex: "je vais partir sur une micro-entreprise", "j'ai choisi SASU", "je suis passé en EURL").

    Args:
        session_id: ID de la session utilisateur
        action: "get" pour consulter, "update" pour modifier
        statut: Le statut juridique choisi (requis pour action="update"). Ex: "micro-entreprise", "SASU", "EURL", "EI", "SARL", "SAS", etc.
    """
    if action == "get":
        current = db.get_statut_juridique(session_id)
        if current:
            return json.dumps({
                "statut_juridique": current,
                "message": f"Statut juridique enregistré : {current}",
            }, ensure_ascii=False)
        return json.dumps({
            "statut_juridique": None,
            "message": "Aucun statut juridique enregistré pour le moment.",
        }, ensure_ascii=False)

    if action == "update":
        statut_clean = statut.strip()
        if not statut_clean:
            return json.dumps({"success": False, "error": "Le paramètre statut est requis pour action='update'"}, ensure_ascii=False)

        ok = db.update_statut_juridique(session_id, statut_clean)
        if not ok:
            return json.dumps({"success": False, "error": "Session introuvable"}, ensure_ascii=False)

        # Mise à jour du cache mémoire aussi
        session = session_manager.get_session(session_id)
        if session:
            session["statut_juridique"] = statut_clean

        logger.info("Statut juridique mis à jour pour session %s : %s", session_id, statut_clean)
        return json.dumps({
            "success": True,
            "statut_juridique": statut_clean,
            "message": f"Statut juridique enregistré : {statut_clean}",
        }, ensure_ascii=False)

    return json.dumps({"success": False, "error": f"Action inconnue : {action}. Utilise 'get' ou 'update'."}, ensure_ascii=False)
