"""
Orchestrateur multi-agent "Agents as Tools".

L'assistant post-onboarding délègue aux sous-agents spécialisés.
Chaque sous-agent est un @tool Strands encapsulant un Agent() avec ses propres outils DB.
Pattern doc: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agents-as-tools/
"""
import logging
from pathlib import Path

from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager

from backend.config import COORDINATOR_MODEL, ORCHESTRATOR_MODEL, SPECIALIST_MODEL, MISTRAL_LARGE, make_model
from backend.session import db as session_db
from backend.tools.objectifs import manage_objectifs
from backend.tools.crm import manage_crm
from backend.tools.budget import manage_budget
from backend.tools.admin import manage_admin
from backend.tools.calendar import manage_calendar
from backend.tools.roadmap import manage_roadmap
from backend.tools.interaction import propose_choices, display_data_table, suggest_specialist_chat, activate_dock_component
from backend.tools.profil import manage_statut_juridique
from backend.agents.financial_swarm import financial_agent

logger = logging.getLogger("kameleon.orchestrator")

# ─── Charger le prompt orchestrateur ───
_PROMPT_PATH = Path(__file__).parent / "prompts" / "orchestrator.txt"
_ORCHESTRATOR_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


# ─── Helper : créer un modèle Mistral ───
def _mistral_model(model_id: str):
    return make_model(model_id)


def _extract_text(result) -> str:
    """Extrait le texte de la réponse d'un agent Strands."""
    try:
        return result.message["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return str(result)


# =====================================================
# Sous-agents comme Tools (pattern Strands "Agents as Tools")
# =====================================================

@tool
def objectifs_agent(query: str) -> str:
    """Gère les objectifs utilisateur : lire, créer, modifier, supprimer, prioriser.

    Args:
        query: La demande de l'utilisateur concernant ses objectifs
    """
    agent = Agent(
        name="objectifs_specialist",
        model=_mistral_model(SPECIALIST_MODEL),
        system_prompt=(
            "Tu es un spécialiste de la gestion d'objectifs. "
            "Tu utilises l'outil manage_objectifs pour lire, créer, modifier ou supprimer des objectifs. "
            "Réponds toujours en français, de manière concise et actionnable."
        ),
        tools=[manage_objectifs],
        callback_handler=None,
    )
    result = agent(query)
    return _extract_text(result)


@tool
def crm_agent(session_id: str, prenom: str, query: str) -> str:
    """Gère le CRM : clients, factures, analyse des impayés, relances, rédaction d'emails de relance.

    Args:
        session_id: ID de la session utilisateur
        prenom: Prénom de l'utilisateur (pour signer les emails)
        query: La demande de l'utilisateur concernant ses clients ou factures
    """
    agent = Agent(
        name="crm_specialist",
        model=_mistral_model(MISTRAL_LARGE),
        system_prompt=(
            f"Tu es un spécialiste CRM. Le session_id est '{session_id}'. "
            f"L'utilisateur s'appelle {prenom}. Signe les emails en son nom.\n"
            "Tu utilises manage_crm pour lire/écrire des données et display_data_table pour afficher les résultats. "
            "Passe TOUJOURS le session_id dans tes appels manage_crm.\n\n"
            "## RÈGLE CRITIQUE : afficher avec display_data_table\n"
            "Pour TOUT résultat de données (factures, clients, impayés), tu DOIS appeler display_data_table.\n"
            "Utilise UNIQUEMENT les données retournées par manage_crm. NE JAMAIS inventer de données.\n"
            "NE JAMAIS écrire de tableau en texte/markdown.\n"
            "Après display_data_table, écris UN résumé court (1 phrase max).\n\n"
            "## INTERDIT\n"
            "- NE JAMAIS proposer de choix ou options (pas de bullet points, pas de 'Tu veux...')\n"
            "- NE JAMAIS lister des actions possibles — l'orchestrateur gère les choix\n"
            "- NE JAMAIS inventer de données. Utilise UNIQUEMENT ce que manage_crm retourne.\n\n"
            "## Lister les factures\n"
            "1. Appelle manage_crm action='list_factures'\n"
            "2. Appelle display_data_table avec les données retournées. "
            "Colonnes : N°, Client, Montant, Statut, Échéance. "
            "Utilise client_nom (pas client_id).\n\n"
            "## Analyser les impayés\n"
            "1. Appelle manage_crm action='analyze_overdue'\n"
            "2. Appelle display_data_table avec les résultats\n"
            "3. Résume le total impayé en 1 phrase\n\n"
            "## Relance client\n"
            "1. get_facture → récupère les détails\n"
            "2. list_reminders → vérifie les brouillons existants\n"
            "3. Rédige un email de relance professionnel (objet + corps) signé par {prenom}\n"
            "4. save_reminder → sauvegarde en BROUILLON\n"
            "5. Affiche le brouillon via display_data_table (title='Brouillon de relance', colonnes Champ/Contenu)\n"
            "Un brouillon n'est PAS un envoi. Ne dis JAMAIS 'relance envoyée'.\n\n"
            "## Envoyer une relance\n"
            "1. mark_reminder_sent avec l'item_id\n"
            "2. Confirme brièvement\n\n"
            "Réponds toujours en français, de manière concise."
        ),
        tools=[manage_crm, display_data_table],
        callback_handler=None,
    )
    result = agent(query)
    return _extract_text(result)


@tool
def budget_agent(session_id: str, query: str) -> str:
    """Gère le budget : consulter, ajouter/supprimer des charges, mettre à jour les revenus.

    Args:
        session_id: ID de la session utilisateur
        query: La demande de l'utilisateur concernant son budget
    """
    agent = Agent(
        name="budget_specialist",
        model=_mistral_model(SPECIALIST_MODEL),
        system_prompt=(
            f"Tu es un spécialiste budget. Le session_id est '{session_id}'. "
            "Tu utilises l'outil manage_budget pour gérer le budget prévisionnel. "
            "Passe toujours le session_id dans tes appels. "
            "Réponds toujours en français."
        ),
        tools=[manage_budget],
        callback_handler=None,
    )
    result = agent(query)
    return _extract_text(result)


@tool
def admin_agent(session_id: str, query: str) -> str:
    """Gère la checklist administrative : lister, ajouter, cocher, supprimer des démarches.

    Args:
        session_id: ID de la session utilisateur
        query: La demande de l'utilisateur concernant ses démarches administratives
    """
    agent = Agent(
        name="admin_specialist",
        model=_mistral_model(SPECIALIST_MODEL),
        system_prompt=(
            f"Tu es un spécialiste administratif. Le session_id est '{session_id}'. "
            "Tu utilises l'outil manage_admin pour gérer la checklist admin. "
            "Passe toujours le session_id dans tes appels. "
            "Réponds toujours en français."
        ),
        tools=[manage_admin],
        callback_handler=None,
    )
    result = agent(query)
    return _extract_text(result)


@tool
def calendar_agent(session_id: str, query: str) -> str:
    """Gère le calendrier : lister, ajouter, modifier, supprimer des événements.

    Args:
        session_id: ID de la session utilisateur
        query: La demande de l'utilisateur concernant son planning
    """
    agent = Agent(
        name="calendar_specialist",
        model=_mistral_model(SPECIALIST_MODEL),
        system_prompt=(
            f"Tu es un spécialiste planning. Le session_id est '{session_id}'. "
            "Tu utilises l'outil manage_calendar pour gérer le calendrier. "
            "Passe toujours le session_id dans tes appels. "
            "Réponds toujours en français."
        ),
        tools=[manage_calendar],
        callback_handler=None,
    )
    result = agent(query)
    return _extract_text(result)


@tool
def roadmap_agent(session_id: str, query: str) -> str:
    """Gère la roadmap : consulter le plan, modifier des phases, marquer des étapes terminées.

    Args:
        session_id: ID de la session utilisateur
        query: La demande de l'utilisateur concernant son plan d'action
    """
    agent = Agent(
        name="roadmap_specialist",
        model=_mistral_model(SPECIALIST_MODEL),
        system_prompt=(
            f"Tu es un spécialiste roadmap. Le session_id est '{session_id}'. "
            "Tu utilises l'outil manage_roadmap pour gérer les phases du plan d'action. "
            "Passe toujours le session_id dans tes appels. "
            "Réponds toujours en français."
        ),
        tools=[manage_roadmap],
        callback_handler=None,
    )
    result = agent(query)
    return _extract_text(result)


# =====================================================
# Orchestrateur
# =====================================================

_orchestrators: dict[str, Agent] = {}


def _build_orchestrator_prompt(session: dict) -> str:
    """Construit le prompt de l'orchestrateur avec le contexte utilisateur."""
    onboarding = session.get("onboarding_data", {})
    prenom = onboarding.get("prenom", "l'utilisateur")
    activite = onboarding.get("activite", "non renseignée")
    plan = onboarding.get("_plan", {})
    objectif_smart = plan.get("objectif_smart", "non défini")
    statut_juridique = session.get("statut_juridique") or "non défini"

    session_id = session['session_id']
    assistant_name = session.get("assistant_name") or "l'assistant"
    user_context = (
        f"- Prénom : {prenom}\n"
        f"- Activité : {activite}\n"
        f"- Objectif SMART : {objectif_smart}\n"
        f"- Statut juridique : {statut_juridique}\n"
        f"- Session ID : {session_id}"
    )
    return (_ORCHESTRATOR_PROMPT_TEMPLATE
            .replace("{assistant_name}", assistant_name)
            .replace("{prenom}", prenom)
            .replace("{user_context}", user_context)
            .replace("{session_id}", session_id))


def _load_saved_messages(session_id: str) -> list[dict]:
    """Charge l'historique des messages SQLite et les convertit au format Strands."""
    saved = session_db.load_messages(session_id, chat_type="main")
    messages = []
    for msg in saved:
        role = msg["role"]
        content = msg["content"]
        if role in ("user", "assistant") and content.strip():
            messages.append({
                "role": role,
                "content": [{"text": content}],
            })
    return messages


def get_or_create_orchestrator(session_id: str, session: dict) -> Agent:
    """
    Retourne l'orchestrateur pour cette session.
    Crée l'agent au premier appel, le réutilise ensuite (historique conservé).
    Au redémarrage du serveur, restaure l'historique depuis SQLite.
    """
    logger.info("get_or_create_orchestrator — session=%s, exists=%s", session_id, session_id in _orchestrators)
    if session_id not in _orchestrators:
        # Restaurer l'historique de conversation depuis SQLite
        saved_messages = _load_saved_messages(session_id)
        logger.info("Restored %d messages from SQLite for session %s", len(saved_messages), session_id)

        _orchestrators[session_id] = Agent(
            name="orchestrator",
            model=_mistral_model(ORCHESTRATOR_MODEL),
            system_prompt=_build_orchestrator_prompt(session),
            tools=[
                objectifs_agent,
                crm_agent,
                budget_agent,
                admin_agent,
                calendar_agent,
                roadmap_agent,
                financial_agent,
                manage_statut_juridique,
                propose_choices,
                display_data_table,
                suggest_specialist_chat,
                activate_dock_component,
            ],
            callback_handler=None,
            conversation_manager=SlidingWindowConversationManager(window_size=40),
            messages=saved_messages if saved_messages else None,
        )
    return _orchestrators[session_id]


def remove_orchestrator(session_id: str) -> None:
    """Libère l'orchestrateur d'une session."""
    _orchestrators.pop(session_id, None)
