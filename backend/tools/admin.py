"""
Tool Strands — gestion de la checklist administrative.
"""
import json

from strands import tool

from backend.session import db


@tool(name="manage_admin")
def manage_admin(
    session_id: str,
    action: str,
    item_id: int = 0,
    data: str = "{}",
) -> str:
    """Gère la checklist administrative de l'utilisateur.

    Args:
        session_id: ID de la session utilisateur
        action: "list", "add", "toggle", "remove"
        item_id: ID de l'item (pour toggle, remove)
        data: JSON avec les données pour add. Champs : label, description, url
    """
    if action == "list":
        items = db.load_admin_checklist(session_id)
        return json.dumps(items, ensure_ascii=False)

    elif action == "add":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        if not fields.get("label"):
            return "Erreur : 'label' requis pour add"
        items = db.load_admin_checklist(session_id)
        items.append({
            "label": fields["label"],
            "description": fields.get("description", ""),
            "url": fields.get("url"),
            "done": False,
        })
        db.save_admin_checklist(session_id, items)
        return f"Item '{fields['label']}' ajouté à la checklist"

    elif action == "toggle":
        if not item_id:
            return "Erreur : item_id requis pour toggle"
        new_done = db.toggle_admin_item(item_id)
        return f"Item {item_id} : {'fait' if new_done else 'à faire'}"

    elif action == "remove":
        if not item_id:
            return "Erreur : item_id requis pour remove"
        items = db.load_admin_checklist(session_id)
        items = [i for i in items if i["id"] != item_id]
        db.save_admin_checklist(session_id, items)
        return f"Item {item_id} supprimé"

    else:
        return f"Erreur : action '{action}' invalide. Actions : list, add, toggle, remove"
