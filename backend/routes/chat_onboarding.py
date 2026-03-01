"""
Endpoint POST /chat/onboarding — exécute le workflow d'onboarding séquentiel.
Émet des SSE step_done pour chaque étape du workflow.
"""
import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.session.manager import session_manager
from backend.session import db
from backend.agents.onboarding_workflow import step_analyse, step_map_tools, step_generate_roadmap, step_build_ui, _merge_and_persist, generate_tool_descriptions

logger = logging.getLogger("kameleon.onboarding")

router = APIRouter()


async def _run_onboarding_workflow(session: dict):
    """
    Exécute le workflow d'onboarding en 3 étapes et émet des SSE.

    Étape 1: Analyse du profil → objectifs priorisés
    Étape 2: Mapping objectifs → outils
    Étape 3: Construction de l'interface personnalisée
    """
    session_id = session["session_id"]
    profile = session.get("onboarding_data", {})

    if not profile or not profile.get("prenom"):
        yield {
            "data": json.dumps({"error": "Profil d'onboarding manquant"}, ensure_ascii=False),
            "event": "error",
        }
        return

    try:
        # ── Étape 1 : Analyse ──
        yield {
            "data": json.dumps({
                "step": 1,
                "label": "Analyse de votre profil",
                "status": "in_progress",
            }, ensure_ascii=False),
            "event": "step_update",
        }

        analyse = step_analyse(profile)

        yield {
            "data": json.dumps({
                "step": 1,
                "label": "Analyse de votre profil",
                "status": "done",
                "summary": analyse.analyse_situation,
            }, ensure_ascii=False),
            "event": "step_done",
        }

        # ── Étape 2 : Mapping des outils ──
        yield {
            "data": json.dumps({
                "step": 2,
                "label": "Identification de vos priorités",
                "status": "in_progress",
            }, ensure_ascii=False),
            "event": "step_update",
        }

        tool_mapping = step_map_tools(profile, analyse)

        nb_objectifs = len(analyse.objectifs)
        nb_outils = len(tool_mapping.outils_dashboard)
        yield {
            "data": json.dumps({
                "step": 2,
                "label": "Identification de vos priorités",
                "status": "done",
                "summary": f"{nb_objectifs} objectifs identifiés, {nb_outils} outils recommandés",
            }, ensure_ascii=False),
            "event": "step_done",
        }

        # ── Persistance des objectifs en DB ──
        _merge_and_persist(analyse, tool_mapping)

        # ── Étape Roadmap : Génération du plan ──
        yield {
            "data": json.dumps({
                "step": 3,
                "label": "Construction de votre roadmap",
                "status": "in_progress",
            }, ensure_ascii=False),
            "event": "step_update",
        }

        roadmap_result = step_generate_roadmap(profile, analyse)

        # Persister la roadmap en DB
        phases_dicts = [p.model_dump() for p in roadmap_result.phases]
        # Première phase = "current", les autres = "future"
        for i, p in enumerate(phases_dicts):
            p["statut"] = "current" if i == 0 else "future"
        db.save_roadmap(session_id, phases_dicts, roadmap_result.objectif_smart)

        yield {
            "data": json.dumps({
                "step": 3,
                "label": "Construction de votre roadmap",
                "status": "done",
                "summary": f"Roadmap en {len(roadmap_result.phases)} phases générée",
            }, ensure_ascii=False),
            "event": "step_done",
        }

        # ── Étape 4 : Construction de l'interface ──
        yield {
            "data": json.dumps({
                "step": 4,
                "label": "Mise en place de votre interface",
                "status": "in_progress",
            }, ensure_ascii=False),
            "event": "step_update",
        }

        active_components = step_build_ui(analyse, tool_mapping, roadmap_result=roadmap_result)

        # Émettre les ui_component events
        for comp in active_components:
            yield {
                "data": json.dumps(comp, ensure_ascii=False),
                "event": "ui_component",
            }

        # Persister active_components dans la session
        session_manager.update_session_state(
            session_id=session_id,
            maturity_level=2,
            active_components=active_components,
        )

        yield {
            "data": json.dumps({
                "step": 4,
                "label": "Mise en place de votre interface",
                "status": "done",
                "summary": "Votre espace personnalisé est prêt",
            }, ensure_ascii=False),
            "event": "step_done",
        }

        # ── Message de bienvenue ──
        prenom = profile.get("prenom", "")
        outils_noms = [c["title"] for c in active_components]
        outils_str = ", ".join(outils_noms[:-1]) + f" et {outils_noms[-1]}" if len(outils_noms) > 1 else outils_noms[0] if outils_noms else ""

        welcome = (
            f"J'ai analysé ton profil et identifié {nb_objectifs} objectifs prioritaires. "
            f"J'ai préparé ton espace avec les outils adaptés : {outils_str}. "
            f"Tu peux me poser des questions ou explorer tes outils."
        )

        db.save_message(session_id, "assistant", welcome, chat_type="main")

        yield {
            "data": json.dumps({"content": welcome}, ensure_ascii=False),
            "event": "welcome_message",
        }

        # ── Done ──
        yield {
            "data": json.dumps({
                "done": True,
                "active_components": active_components,
            }, ensure_ascii=False),
            "event": "done",
        }

    except Exception as exc:
        logger.exception("Erreur workflow onboarding")
        yield {
            "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            "event": "error",
        }


@router.post("/chat/onboarding")
async def chat_onboarding(session_id: str):
    """
    Lance le workflow d'onboarding pour la session donnée.
    Le profil doit déjà être dans onboarding_data de la session.
    """
    session = session_manager.get_or_create_session(session_id)
    return EventSourceResponse(_run_onboarding_workflow(session))


async def _run_tool_showcase(session: dict):
    """
    Génère des descriptions LLM personnalisées pour chaque outil du dashboard.
    Émet un event tool_description par outil, puis un event done.
    """
    profile = session.get("onboarding_data", {})
    active_components = session.get("active_components", [])

    if not active_components:
        yield {
            "data": json.dumps({"error": "Aucun outil actif dans la session"}, ensure_ascii=False),
            "event": "error",
        }
        return

    try:
        descriptions = generate_tool_descriptions(profile, active_components)

        for tool_desc in descriptions:
            yield {
                "data": json.dumps(tool_desc, ensure_ascii=False),
                "event": "tool_description",
            }

        yield {
            "data": json.dumps({"done": True}, ensure_ascii=False),
            "event": "done",
        }

    except Exception as exc:
        logger.exception("Erreur tool showcase")
        yield {
            "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            "event": "error",
        }


@router.post("/chat/tool-showcase")
async def chat_tool_showcase(session_id: str):
    """
    Génère les descriptions personnalisées des outils pour l'animation de présentation.
    La session doit déjà contenir active_components (post-workflow).
    """
    session = session_manager.get_session(session_id)
    if session is None:
        session = session_manager.get_or_create_session(session_id)
    return EventSourceResponse(_run_tool_showcase(session))


@router.post("/chat/inject-onboarding")
async def inject_onboarding(body: dict):
    """
    Endpoint de test : injecte onboarding_data dans la session.
    """
    session_id = body.get("session_id")
    profile = body.get("profile", {})

    session = session_manager.get_session(session_id)
    if session is None:
        return {"error": "Session introuvable"}

    session_manager.update_session_state(
        session_id=session_id,
        onboarding_data=profile,
    )
    return {"ok": True, "session_id": session_id}
