"""
Tool Strands — interaction HITL (Human-In-The-Loop).

Permet à l'orchestrateur de proposer des choix à l'utilisateur
via un événement SSE poussé dans le stream.

Mécanisme : le tool écrit dans un buffer module-level,
la route streaming le lit et le vide après chaque requête.
"""
import json
import logging

from strands import tool

logger = logging.getLogger("kameleon.tools.interaction")

# Buffer partagé — la route streaming le lit et le vide
_pending_events: list[dict] = []


def get_and_clear_interaction_events() -> list[dict]:
    """Récupère et vide les événements interaction en attente."""
    events = list(_pending_events)
    _pending_events.clear()
    return events


def push_data_table(title: str, columns: list[str], rows: list[list], summary: str = ""):
    """Pousse un tableau de données à afficher dans le chat."""
    _pending_events.append({
        "type": "data_table",
        "title": title,
        "columns": columns,
        "rows": rows,
        "summary": summary,
    })


@tool(name="propose_choices")
def propose_choices(
    question: str,
    choices: str,
) -> str:
    """Propose des choix à l'utilisateur via l'interface (boutons cliquables).

    Args:
        question: La question à poser à l'utilisateur
        choices: JSON array de choix, chaque choix est un objet avec "id" et "label", par exemple: [{"id": "a", "label": "Option A"}, {"id": "b", "label": "Option B"}]
    """
    try:
        choices_list = json.loads(choices)
    except json.JSONDecodeError:
        return "Erreur : choices n'est pas du JSON valide"

    interaction_event = {
        "type": "choice",
        "question": question,
        "choices": choices_list,
    }

    _pending_events.append(interaction_event)
    logger.info("propose_choices called: %s (%d choices)", question, len(choices_list))

    labels = [c.get("label", c.get("id", "?")) for c in choices_list]
    return f"Choix proposés à l'utilisateur : {', '.join(labels)}. Attends sa réponse dans le prochain message."


@tool(name="activate_dock_component")
def activate_dock_component(
    session_id: str,
    component_type: str,
    title: str,
    icon: str,
    data: str = "{}",
) -> str:
    """Active un nouveau composant dans le dock de l'utilisateur.

    Utilise cet outil AVANT suggest_specialist_chat quand le composant
    n'existe pas encore dans le dock (ex: prévisions après calcul financier).

    Args:
        session_id: ID de la session utilisateur
        component_type: Type du composant — "previsions", "admin", "calendar", "crm", "budget", "roadmap", "chat", "objectifs"
        title: Titre affiché dans le dock (ex: "Prévisions Financières")
        icon: Emoji affiché dans le dock (ex: "📊")
        data: Données JSON du composant (optionnel)
    """
    from backend.session import db as session_db

    try:
        parsed_data = json.loads(data) if data and data != "{}" else None
    except json.JSONDecodeError:
        parsed_data = None

    new_component = {
        "action": "activate",
        "type": component_type,
        "id": f"{component_type}-1",
        "title": title,
        "icon": icon,
        "data": parsed_data,
    }

    # Mettre à jour active_components en DB
    session = session_db.load_session(session_id)
    if session:
        components = session.get("active_components", [])
        # Ne pas ajouter un doublon
        existing_types = {c.get("type") for c in components}
        if component_type not in existing_types:
            components.append(new_component)
            session_db.save_session(
                session_id=session_id,
                persona=session.get("persona", "creator"),
                assistant_name=session.get("assistant_name"),
                maturity_level=session.get("maturity_level", 2),
                onboarding_data=session.get("onboarding_data", {}),
                active_components=components,
                statut_juridique=session.get("statut_juridique"),
            )

    # Pousser l'event SSE pour le frontend
    _pending_events.append({
        "type": "activate_component",
        "component_type": component_type,
        "id": new_component["id"],
        "title": title,
        "icon": icon,
        "data": parsed_data,
    })
    logger.info("activate_dock_component: %s '%s' %s", component_type, title, icon)
    return f"Composant '{title}' ({component_type}) activé dans le dock."


@tool(name="suggest_specialist_chat")
def suggest_specialist_chat(
    tool_id: str,
    message: str,
) -> str:
    """Suggère à l'utilisateur d'ouvrir un outil spécifique du dock en faisant rebondir son icône.

    Utilise cet outil quand la question de l'utilisateur relève d'un domaine spécialisé
    et qu'il devrait ouvrir l'outil correspondant dans le dock (ex: chat spécialiste, admin, budget).

    Args:
        tool_id: L'identifiant de l'outil à mettre en avant (ex: "chat", "admin", "budget", "crm", "calendar", "roadmap", "objectifs")
        message: Le message explicatif à afficher à l'utilisateur pour l'inviter à ouvrir l'outil
    """
    _pending_events.append({
        "type": "dock_bounce",
        "tool_id": tool_id,
        "message": message,
    })
    logger.info("suggest_specialist_chat: bounce %s — %s", tool_id, message)
    return f"Suggestion envoyée à l'utilisateur : ouvrir l'outil '{tool_id}'. Message : {message}"


@tool(name="display_data_table")
def display_data_table(
    title: str,
    columns: str,
    rows: str,
    summary: str = "",
) -> str:
    """Affiche un tableau de données dans l'interface utilisateur (A2UI).

    Args:
        title: Titre du tableau (ex: "Factures en retard")
        columns: JSON array des noms de colonnes, ex: ["N°", "Client", "Montant", "Échéance"]
        rows: JSON array de arrays, chaque sous-array est une ligne, ex: [["FAC-001", "Dupont", "500 €", "2026-01-15"]]
        summary: Texte de synthèse affiché sous le tableau (ex: "Total : 2 450 € d'impayés")
    """
    try:
        cols = json.loads(columns)
        data_rows = json.loads(rows)
    except json.JSONDecodeError:
        return "Erreur : columns ou rows n'est pas du JSON valide"

    _pending_events.append({
        "type": "data_table",
        "title": title,
        "columns": cols,
        "rows": data_rows,
        "summary": summary,
    })
    logger.info("display_data_table: %s (%d rows)", title, len(data_rows))
    return f"Tableau '{title}' affiché à l'utilisateur ({len(data_rows)} lignes)."
