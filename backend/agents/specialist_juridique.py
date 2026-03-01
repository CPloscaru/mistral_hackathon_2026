"""
Agent spécialiste juridique — chat dédié aux questions de statut,
réglementation, taxes et démarches pour entrepreneurs français.

Dispose d'un outil web_search (Brave API) pour chercher des infos à jour.
Chaque session a son propre agent (historique conservé).
"""
import logging

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

from backend.config import COORDINATOR_MODEL, make_model
from backend.tools.web_search import web_search
from backend.tools.profil import manage_statut_juridique

logger = logging.getLogger("kameleon.specialist_juridique")

SYSTEM_PROMPT = """\
Tu es un conseiller expert en création d'entreprise et statuts juridiques en France.

## Ton rôle
Tu aides {prenom} à comprendre et choisir le meilleur statut juridique pour son activité.
Tu connais en détail les statuts français : micro-entreprise (auto-entrepreneur), EI, EIRL, EURL, SASU, SARL, SAS, SA, etc.

## Tes compétences
- Statuts juridiques : avantages, inconvénients, seuils de CA, régimes fiscaux
- Fiscalité : TVA, impôt sur le revenu vs IS, versement libératoire, CFE
- Charges sociales : URSSAF, cotisations, taux par statut
- Démarches de création : immatriculation, CFE, greffe, INPI
- Aides : ACRE, ARE, ARCE, aides régionales
- Protection du patrimoine, responsabilité limitée vs illimitée

## Consulter ou enregistrer le statut juridique
- Pour CONSULTER le statut actuel : `manage_statut_juridique(session_id="{session_id}", action="get")`
- Pour ENREGISTRER un nouveau statut : `manage_statut_juridique(session_id="{session_id}", action="update", statut="...")`

Quand {prenom} annonce clairement son choix de statut juridique (ex: "je pars sur micro-entreprise", "j'ai décidé SASU", "je reste en EI"), tu DOIS :
1. Appeler l'outil avec action="update" pour l'enregistrer
2. Confirmer à {prenom} que c'est noté et le rassurer : ce n'est pas gravé dans le marbre, il pourra toujours évoluer vers un autre statut plus tard si son activité le justifie
3. NE PAS appeler action="update" si {prenom} hésite encore ou pose juste des questions — uniquement quand il/elle affirme son choix

Quand {prenom} demande quel est son statut juridique enregistré, appelle action="get".

## Règles
- Tu tutoies TOUJOURS {prenom}
- Tu es chaleureux, direct et pragmatique
- Tu parles en français courant, jamais robotique
- Tu es concis mais complet : tu donnes les informations clés sans noyer l'utilisateur
- Quand tu n'es pas sûr d'une information (montant, seuil, date), utilise l'outil web_search pour vérifier
- Tu cites tes sources quand tu utilises web_search
- Tu poses des questions de clarification si nécessaire (type d'activité, CA prévisionnel, situation actuelle)
- IMPORTANT : ne donne JAMAIS de conseil fiscal définitif — recommande toujours de vérifier avec un expert-comptable pour les décisions finales

## Contexte utilisateur
{user_context}
"""

_specialist_agents: dict[str, Agent] = {}


def get_or_create_specialist_juridique(session_id: str, session: dict) -> Agent:
    """
    Retourne l'agent spécialiste juridique pour cette session.
    Crée l'agent au premier appel, le réutilise ensuite (historique conservé).
    """
    if session_id not in _specialist_agents:
        onboarding = session.get("onboarding_data", {})
        prenom = onboarding.get("prenom", "l'utilisateur")
        activite = onboarding.get("activite", "non renseignée")
        experience = onboarding.get("experience", "non renseignée")
        situation = onboarding.get("situation", "non renseignée")
        statut_admin = onboarding.get("statut_administratif", "non renseigné")
        statut_souhaite = onboarding.get("statut_souhaite", "non renseigné")
        statut_juridique = session.get("statut_juridique") or "non défini"
        clients = onboarding.get("clients", "non renseigné")
        blocages = onboarding.get("blocages", [])
        objectif = onboarding.get("objectif", "non renseigné")
        plan = onboarding.get("_plan", {})
        objectif_smart = plan.get("objectif_smart", "")

        blocages_str = ", ".join(blocages) if isinstance(blocages, list) else str(blocages)

        user_context_parts = [
            f"- Prénom : {prenom}",
            f"- Activité : {activite}",
            f"- Expérience : {experience}",
            f"- Situation actuelle : {situation}",
            f"- Statut administratif actuel : {statut_admin}",
            f"- Statut souhaité : {statut_souhaite}",
            f"- Statut juridique enregistré : {statut_juridique}",
            f"- Clients existants : {clients}",
            f"- Blocages identifiés : {blocages_str}",
            f"- Objectif principal : {objectif}",
            f"- Session ID : {session_id}",
        ]
        if objectif_smart:
            user_context_parts.append(f"- Objectif SMART : {objectif_smart}")

        user_context = "\n".join(user_context_parts)

        prompt = (SYSTEM_PROMPT
                  .replace("{prenom}", prenom)
                  .replace("{session_id}", session_id)
                  .replace("{user_context}", user_context))

        _specialist_agents[session_id] = Agent(
            name="specialist_juridique",
            model=make_model(COORDINATOR_MODEL),
            system_prompt=prompt,
            tools=[web_search, manage_statut_juridique],
            callback_handler=None,
            conversation_manager=SlidingWindowConversationManager(window_size=30),
        )
        logger.info("Specialist juridique créé pour session %s", session_id)

    return _specialist_agents[session_id]


def remove_specialist_juridique(session_id: str) -> None:
    """Libère l'agent spécialiste d'une session."""
    _specialist_agents.pop(session_id, None)
