"""
Tool Strands — gestion de la roadmap.
"""
import json

from strands import tool

from backend.session import db


@tool(name="manage_roadmap")
def manage_roadmap(
    session_id: str,
    action: str,
    phase_index: int = -1,
    data: str = "{}",
) -> str:
    """Gère la roadmap de l'utilisateur (phases du plan d'action).

    Args:
        session_id: ID de la session utilisateur
        action: "get", "update_phase", "mark_complete", "add_phase", "remove_phase"
        phase_index: Index de la phase (pour update_phase, mark_complete, remove_phase)
        data: JSON avec les données. Pour update_phase : titre, objectif, actions, statut. Pour add_phase : titre, objectif, actions
    """
    if action == "get":
        roadmap = db.load_roadmap(session_id)
        return json.dumps(roadmap, ensure_ascii=False)

    elif action == "update_phase":
        if phase_index < 0:
            return "Erreur : phase_index requis pour update_phase"
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        ok = db.update_roadmap_phase(session_id, phase_index, **fields)
        if ok:
            return f"Phase {phase_index} mise à jour"
        return f"Erreur : phase {phase_index} introuvable"

    elif action == "mark_complete":
        if phase_index < 0:
            return "Erreur : phase_index requis pour mark_complete"
        ok = db.update_roadmap_phase(session_id, phase_index, statut="terminee")
        if ok:
            return f"Phase {phase_index} marquée comme terminée"
        return f"Erreur : phase {phase_index} introuvable"

    elif action == "add_phase":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        if not fields.get("titre"):
            return "Erreur : 'titre' requis pour add_phase"
        new_index = db.add_roadmap_phase(
            session_id=session_id,
            titre=fields["titre"],
            objectif=fields.get("objectif", ""),
            actions=fields.get("actions", []),
        )
        return f"Phase ajoutée à l'index {new_index}"

    elif action == "remove_phase":
        if phase_index < 0:
            return "Erreur : phase_index requis pour remove_phase"
        ok = db.remove_roadmap_phase(session_id, phase_index)
        if ok:
            return f"Phase {phase_index} supprimée"
        return f"Erreur : phase {phase_index} introuvable"

    else:
        return f"Erreur : action '{action}' invalide. Actions : get, update_phase, mark_complete, add_phase, remove_phase"
