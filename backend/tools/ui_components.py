"""
Tool A2UI — manage_ui_component.

Permet à l'agent de contrôler les composants UI du dashboard utilisateur
via invocation_state partagé dans le Swarm Strands.
"""
import logging
from strands import tool, ToolContext

logger = logging.getLogger("kameleon.a2ui")

VALID_TYPES = {"admin", "calendar", "crm", "budget", "roadmap", "chat", "objectifs", "previsions"}
VALID_ACTIONS = {"activate", "deactivate", "update"}


@tool(name="manage_ui_component", context=True)
def manage_ui_component(
    action: str,
    component_type: str,
    title: str = "",
    icon: str = "",
    data: str = "{}",
    tool_context: ToolContext = None,
) -> str:
    """Gère les composants UI du dashboard utilisateur.

    Utilise cet outil pour activer, mettre à jour ou désactiver un composant
    dans le dashboard de l'utilisateur.

    Args:
        action: "activate" pour ajouter un composant, "update" pour modifier ses données, "deactivate" pour le retirer
        component_type: Type du composant — "admin", "calendar", "crm", "budget", "roadmap"
        title: Titre affiché dans le dock (ex: "Budget Prévisionnel"). Requis pour activate.
        icon: Emoji affiché dans le dock (ex: "💰"). Requis pour activate.
        data: Données JSON du composant (ex: charges budget, phases roadmap). Chaîne JSON.
    """
    import json as _json

    logger.info("🎛️ manage_ui_component called: action=%s type=%s title=%s icon=%s data=%s",
                action, component_type, title, icon, data[:200] if data else "None")

    if action not in VALID_ACTIONS:
        return f"Erreur : action '{action}' invalide. Utilise: {VALID_ACTIONS}"
    if component_type not in VALID_TYPES:
        return f"Erreur : type '{component_type}' invalide. Utilise: {VALID_TYPES}"

    # Parser les données JSON
    try:
        parsed_data = _json.loads(data) if data and data != "{}" else None
    except _json.JSONDecodeError:
        parsed_data = None

    event = {
        "action": action,
        "type": component_type,
        "id": f"{component_type}-1",
        "title": title,
        "icon": icon,
        "data": parsed_data,
    }

    # Pousser dans la liste partagée via invocation_state
    ui_events = tool_context.invocation_state.get("ui_events")
    if ui_events is not None:
        ui_events.append(event)

    if action == "activate":
        return f"Composant {component_type} '{title}' activé dans le dashboard."
    elif action == "update":
        return f"Composant {component_type} mis à jour."
    else:
        return f"Composant {component_type} désactivé."
