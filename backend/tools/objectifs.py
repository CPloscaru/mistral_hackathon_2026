"""
Tool Strands — gestion des objectifs utilisateur.

Permet aux agents de lire, modifier et supprimer des objectifs
via la base de données SQLite.
"""
import json
import logging

from strands import tool

from backend.session import db

logger = logging.getLogger("kameleon.tools.objectifs")


@tool(name="manage_objectifs")
def manage_objectifs(
    action: str,
    objectif_id: int = 0,
    data: str = "{}",
) -> str:
    """Gère les objectifs de l'utilisateur dans la base de données.

    Args:
        action: "list" pour lister, "create" pour créer, "get" pour un objectif, "update" pour modifier, "delete" pour supprimer
        objectif_id: ID de l'objectif (requis pour get, update, delete)
        data: JSON avec les champs. Pour create : rang, objectif, urgence, impact (requis), justification, tool_type, raison (optionnels). Pour update : rang, objectif, urgence, impact, justification, tool_type, raison, statut
    """
    if action == "list":
        objectifs = db.load_objectifs()
        return json.dumps(objectifs, ensure_ascii=False)

    elif action == "create":
        try:
            fields = json.loads(data) if data and data != "{}" else {}
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        required = ["rang", "objectif", "urgence", "impact"]
        missing = [k for k in required if k not in fields]
        if missing:
            return f"Erreur : champs requis manquants : {', '.join(missing)}"
        new_id = db.create_objectif(
            rang=fields["rang"],
            objectif=fields["objectif"],
            urgence=fields["urgence"],
            impact=fields["impact"],
            justification=fields.get("justification"),
            tool_type=fields.get("tool_type"),
            raison=fields.get("raison"),
        )
        return f"Objectif créé avec id={new_id}"

    elif action == "get":
        if not objectif_id:
            return "Erreur : objectif_id requis pour get"
        obj = db.get_objectif(objectif_id)
        if obj is None:
            return f"Erreur : objectif {objectif_id} introuvable"
        return json.dumps(obj, ensure_ascii=False)

    elif action == "update":
        if not objectif_id:
            return "Erreur : objectif_id requis pour update"
        try:
            fields = json.loads(data) if data and data != "{}" else {}
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        if not fields:
            return "Erreur : aucun champ à modifier"
        ok = db.update_objectif(objectif_id, **fields)
        if ok:
            return f"Objectif {objectif_id} mis à jour"
        return f"Erreur : objectif {objectif_id} introuvable"

    elif action == "delete":
        if not objectif_id:
            return "Erreur : objectif_id requis pour delete"
        ok = db.delete_objectif(objectif_id)
        if ok:
            return f"Objectif {objectif_id} supprimé"
        return f"Erreur : objectif {objectif_id} introuvable"

    else:
        return f"Erreur : action '{action}' invalide. Utilise : list, create, get, update, delete"
