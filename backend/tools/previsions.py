"""
Tool Strands — gestion des prévisions financières.
"""
import json
import logging

from strands import tool

from backend.session import db

logger = logging.getLogger("kameleon.tools.previsions")


@tool(name="manage_previsions")
def manage_previsions(
    session_id: str,
    action: str,
    data: str = "{}",
) -> str:
    """Gère les prévisions financières de l'utilisateur.

    Args:
        session_id: ID de la session utilisateur
        action: "save", "get"
        data: JSON avec les données pour save:
              {
                "objectif_net": 36000,
                "ca_brut_cible": 46272,
                "taux_cotisations": 0.222,
                "cotisations_montant": 10272,
                "ca_actuel": 18600,
                "ca_manquant": 27672,
                "tjm_moyen": 450,
                "missions_restantes": 8,
                "jours_restants": 62,
                "statut_juridique": "micro-entreprise",
                "source_cotisations": "URSSAF 2026 — taux BNC 22.2%",
                "details": {
                  "factures_payees": 12600,
                  "factures_en_attente": 6000,
                  "nb_clients": 5,
                  "formule": "CA_brut = objectif_net / (1 - taux_cotisations)"
                }
              }
    """
    logger.info("manage_previsions called — session=%s, action=%s, data_len=%d", session_id, action, len(data))

    if action == "get":
        previsions = db.load_previsions(session_id)
        logger.info("previsions GET — found=%s", previsions is not None)
        if previsions is None:
            return "Aucune prévision financière trouvée pour cette session."
        return json.dumps(previsions, ensure_ascii=False)

    elif action == "save":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error("previsions SAVE — JSON decode error: %s, data=%s", e, data[:200])
            return "Erreur : data n'est pas du JSON valide"
        logger.info("previsions SAVE — fields keys=%s", list(fields.keys()))
        db.save_previsions(session_id, fields)
        logger.info("previsions SAVE — OK")
        return "Prévisions financières sauvegardées avec succès."

    else:
        logger.warning("previsions — action invalide: %s", action)
        return f"Erreur : action '{action}' invalide. Actions : get, save"
