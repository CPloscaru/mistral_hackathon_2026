"""
Tool Strands — gestion du calendrier.
"""
import json

from strands import tool

from backend.session import db


@tool(name="manage_calendar")
def manage_calendar(
    session_id: str,
    action: str,
    item_id: int = 0,
    data: str = "{}",
) -> str:
    """Gère le calendrier de l'utilisateur.

    Args:
        session_id: ID de la session utilisateur
        action: "list", "add", "update", "remove"
        item_id: ID de l'événement (pour update, remove)
        data: JSON avec les données. Pour add/update : date, titre, description, type
    """
    if action == "list":
        events = db.load_calendar_events(session_id)
        return json.dumps(events, ensure_ascii=False)

    elif action == "add":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        if not fields.get("date") or not fields.get("titre"):
            return "Erreur : 'date' et 'titre' requis pour add"
        events = db.load_calendar_events(session_id)
        events.append({
            "date": fields["date"],
            "titre": fields["titre"],
            "description": fields.get("description", ""),
            "type": fields.get("type", "action"),
        })
        db.save_calendar_events(session_id, events)
        return f"Événement '{fields['titre']}' ajouté le {fields['date']}"

    elif action == "update":
        if not item_id:
            return "Erreur : item_id requis pour update"
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        events = db.load_calendar_events(session_id)
        found = False
        for ev in events:
            if ev["id"] == item_id:
                for k in ("date", "titre", "description", "type"):
                    if k in fields:
                        ev[k] = fields[k]
                found = True
                break
        if not found:
            return f"Erreur : événement {item_id} introuvable"
        db.save_calendar_events(session_id, events)
        return f"Événement {item_id} mis à jour"

    elif action == "remove":
        if not item_id:
            return "Erreur : item_id requis pour remove"
        events = db.load_calendar_events(session_id)
        events = [e for e in events if e["id"] != item_id]
        db.save_calendar_events(session_id, events)
        return f"Événement {item_id} supprimé"

    else:
        return f"Erreur : action '{action}' invalide. Actions : list, add, update, remove"
