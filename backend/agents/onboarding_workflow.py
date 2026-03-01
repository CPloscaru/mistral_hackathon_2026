"""
Workflow séquentiel d'onboarding — alternative au Swarm.

Utilise le pattern workflow de Strands Agents SDK :
chaque étape est un Agent spécialisé, l'output de l'un alimente le suivant.

Étape 1 : Analyste — lit le profil, identifie objectifs et priorités.
Étape 2 : Tool Mapper — assigne un outil à chaque objectif (context passing).

Usage:
    source venv/bin/activate
    python -m backend.agents.onboarding_workflow [--profile PATH]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent

from backend.config import COORDINATOR_MODEL, MODEL_8B, make_model
from backend.agents.prompts import WORKFLOW_ANALYST_PROMPT, WORKFLOW_TOOL_MAPPER_PROMPT, WORKFLOW_ROADMAP_PROMPT
from backend.session import db

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("kameleon.workflow")

DEFAULT_PROFILE = Path(__file__).resolve().parent.parent.parent / "tests" / "workflow_onboarding" / "inputs" / "profile.json"

MAX_RETRIES = 2


# ─── Schémas Pydantic ────────────────────────────────────────────────

class Objectif(BaseModel):
    rang: int
    objectif: str
    urgence: Literal["haute", "moyenne", "basse"]
    impact: Literal["haut", "moyen", "bas"]
    justification: str


class AnalyseResult(BaseModel):
    analyse_situation: str
    objectifs: list[Objectif] = Field(min_length=4, max_length=8)


VALID_TOOL_TYPES = Literal["chat", "crm", "admin", "budget", "roadmap", "calendar", "previsions"]


class ToolAssignation(BaseModel):
    rang: int
    objectif: str
    tool_type: VALID_TOOL_TYPES
    raison: str


class DashboardTool(BaseModel):
    tool_type: VALID_TOOL_TYPES
    title: str
    icon: str
    couvre_objectifs: list[int]


class ToolMappingResult(BaseModel):
    assignations: list[ToolAssignation] = Field(min_length=4)
    outils_dashboard: list[DashboardTool] = Field(min_length=1)


# ─── Helpers ──────────────────────────────────────────────────────────

def extract_json(text: str) -> dict | None:
    """Extrait le premier bloc JSON valide d'un texte."""
    match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    depth = 0
    start = None
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = None
    return None


T = type  # alias pour le type hint générique


def parse_and_validate(text: str, model: type[BaseModel]) -> BaseModel:
    """Extrait le JSON et le valide avec un modèle Pydantic. Lève ValueError si échec."""
    raw = extract_json(text)
    if raw is None:
        raise ValueError(f"Pas de JSON trouvé dans la réponse:\n{text[:500]}")
    return model(**raw)


# ─── Étape 1 : Analyste ──────────────────────────────────────────────

def step_analyse(profile: dict) -> AnalyseResult:
    """Analyse le profil et retourne les objectifs priorisés (validés par Pydantic)."""
    logger.info("Étape 1 — Analyse du profil de %s", profile.get("prenom", "?"))

    analyst = Agent(
        name="analyst",
        model=make_model(COORDINATOR_MODEL, max_tokens=10000),
        system_prompt=WORKFLOW_ANALYST_PROMPT,
        callback_handler=None,
    )

    profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
    prompt = f"<profile_json>\n{profile_str}\n</profile_json>"

    for attempt in range(1, MAX_RETRIES + 1):
        result = analyst(prompt)
        result_text = str(result)
        try:
            return parse_and_validate(result_text, AnalyseResult)
        except (ValueError, Exception) as e:
            logger.warning("Tentative %d/%d — validation échouée: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                prompt = (
                    f"Ta réponse précédente n'est pas un JSON valide conforme au schéma.\n"
                    f"Erreur: {e}\n\n"
                    f"Renvoie UNIQUEMENT le JSON corrigé, sans texte autour."
                )
            else:
                logger.error("Échec après %d tentatives", MAX_RETRIES)
                logger.error("Dernière réponse:\n%s", result_text)
                sys.exit(1)


# ─── Étape 2 : Tool Mapper ────────────────────────────────────────────

def step_map_tools(profile: dict, analyse: AnalyseResult) -> ToolMappingResult:
    """Assigne un outil à chaque objectif en passant le contexte du step 1."""
    logger.info("Étape 2 — Mapping des outils pour %d objectifs", len(analyse.objectifs))

    mapper = Agent(
        name="tool_mapper",
        model=make_model(COORDINATOR_MODEL, max_tokens=10000),
        system_prompt=WORKFLOW_TOOL_MAPPER_PROMPT,
        callback_handler=None,
    )

    # Context passing : on envoie le profil + l'output complet du step 1
    context = {
        "profil": profile,
        "analyse": analyse.model_dump(),
    }
    context_str = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = f"<contexte_workflow>\n{context_str}\n</contexte_workflow>"

    for attempt in range(1, MAX_RETRIES + 1):
        result = mapper(prompt)
        result_text = str(result)
        try:
            return parse_and_validate(result_text, ToolMappingResult)
        except (ValueError, Exception) as e:
            logger.warning("Tentative %d/%d — validation échouée: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                prompt = (
                    f"Ta réponse précédente n'est pas un JSON valide conforme au schéma.\n"
                    f"Erreur: {e}\n\n"
                    f"Renvoie UNIQUEMENT le JSON corrigé, sans texte autour."
                )
            else:
                logger.error("Échec après %d tentatives", MAX_RETRIES)
                logger.error("Dernière réponse:\n%s", result_text)
                sys.exit(1)


# ─── Schémas Pydantic — Roadmap ──────────────────────────────────────

class RoadmapPhase(BaseModel):
    titre: str
    objectif: str
    actions: list[str] = Field(min_length=3, max_length=5)


class RoadmapResult(BaseModel):
    objectif_smart: str
    phases: list[RoadmapPhase] = Field(min_length=3, max_length=5)


# ─── Étape Roadmap : Génération du plan ──────────────────────────────

def step_generate_roadmap(profile: dict, analyse: AnalyseResult) -> RoadmapResult:
    """Génère une roadmap personnalisée basée sur le profil et l'analyse."""
    logger.info("Étape Roadmap — Génération du plan pour %s", profile.get("prenom", "?"))

    roadmap_agent = Agent(
        name="roadmap_builder",
        model=make_model(COORDINATOR_MODEL, max_tokens=10000),
        system_prompt=WORKFLOW_ROADMAP_PROMPT,
        callback_handler=None,
    )

    context = {
        "profil": profile,
        "analyse": analyse.model_dump(),
    }
    context_str = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = f"<contexte_workflow>\n{context_str}\n</contexte_workflow>"

    for attempt in range(1, MAX_RETRIES + 1):
        result = roadmap_agent(prompt)
        result_text = str(result)
        try:
            return parse_and_validate(result_text, RoadmapResult)
        except (ValueError, Exception) as e:
            logger.warning("Roadmap — tentative %d/%d: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                prompt = (
                    f"Ta réponse précédente n'est pas un JSON valide conforme au schéma.\n"
                    f"Erreur: {e}\n\n"
                    f"Renvoie UNIQUEMENT le JSON corrigé, sans texte autour."
                )
            else:
                logger.error("Échec roadmap après %d tentatives", MAX_RETRIES)
                logger.error("Dernière réponse:\n%s", result_text)
                sys.exit(1)


# ─── Persistance ──────────────────────────────────────────────────────

def _merge_and_persist(
    analyse: AnalyseResult,
    tool_mapping: ToolMappingResult,
) -> list[int]:
    """Agrège step1 + step2 et persiste les objectifs en DB.

    Fusionne chaque objectif (rang, urgence, impact, justification)
    avec son assignation d'outil (tool_type, raison) puis sauvegarde.

    Returns:
        Liste des ids insérés en DB.
    """
    assignation_by_rang = {a.rang: a for a in tool_mapping.assignations}

    rows = []
    for obj in analyse.objectifs:
        assignation = assignation_by_rang.get(obj.rang)
        rows.append({
            "rang": obj.rang,
            "objectif": obj.objectif,
            "urgence": obj.urgence,
            "impact": obj.impact,
            "justification": obj.justification,
            "tool_type": assignation.tool_type if assignation else None,
            "raison": assignation.raison if assignation else None,
        })

    ids = db.save_objectifs(rows)
    logger.info("Persisté %d objectifs en DB", len(ids))
    return ids


# ─── Étape 3 : UI Builder (déterministe) ─────────────────────────────

def step_build_ui(analyse: AnalyseResult, tool_mapping: ToolMappingResult, roadmap_result: RoadmapResult | None = None) -> list[dict]:
    """Transforme le ToolMappingResult en active_components format A2UI.

    Pour chaque DashboardTool, crée un dict compatible avec les SSE ui_component events.
    Enrichit les data avec les objectifs détaillés couverts par l'outil.
    Si roadmap_result est fourni, injecte les phases dans le composant roadmap.

    Returns:
        Liste de dicts au format A2UI (action, type, id, title, icon, data).
    """
    logger.info("Étape 3 — Construction de l'interface (%d outils)", len(tool_mapping.outils_dashboard))

    # Index des objectifs par rang pour enrichir les data
    objectifs_by_rang = {obj.rang: obj for obj in analyse.objectifs}

    components = []
    for tool in tool_mapping.outils_dashboard:
        # Objectifs détaillés couverts par cet outil
        objectifs_detail = []
        for rang in tool.couvre_objectifs:
            obj = objectifs_by_rang.get(rang)
            if obj:
                objectifs_detail.append(obj.objectif)

        comp_data = {
            "couvre_objectifs": tool.couvre_objectifs,
            "objectifs": objectifs_detail,
        }

        # Les composants "chat" sont routés vers un agent spécialiste dédié
        if tool.tool_type == "chat":
            comp_data["chat_type"] = "specialist_juridique"

        # Injecter les phases roadmap dans le composant roadmap
        if tool.tool_type == "roadmap" and roadmap_result:
            comp_data["phases"] = [p.model_dump() for p in roadmap_result.phases]
            comp_data["objectif_smart"] = roadmap_result.objectif_smart

        components.append({
            "action": "activate",
            "type": tool.tool_type,
            "id": f"{tool.tool_type}-1",
            "title": tool.title,
            "icon": tool.icon,
            "data": comp_data,
        })

    # Toujours injecter l'outil Objectifs en premier
    components.insert(0, {
        "action": "activate",
        "type": "objectifs",
        "id": "objectifs-1",
        "title": "Mes Objectifs",
        "icon": "\U0001F3AF",
        "data": None,
    })

    return components


# ─── Tool Showcase — descriptions LLM ────────────────────────────────

class ToolDescription(BaseModel):
    type: str
    description: str


class ToolDescriptionsResult(BaseModel):
    descriptions: list[ToolDescription] = Field(min_length=1)


def generate_tool_descriptions(profile: dict, tools: list[dict]) -> list[dict]:
    """Génère une description courte personnalisée pour chaque outil via LLM (MODEL_8B).

    Args:
        profile: Le profil utilisateur (prenom, activite, etc.)
        tools: Liste des active_components (type, title, icon, data.objectifs)

    Returns:
        Liste de dicts {type, title, icon, description}
    """
    logger.info("Génération des descriptions pour %d outils", len(tools))

    tools_summary = []
    for t in tools:
        objectifs = (t.get("data") or {}).get("objectifs", [])
        tools_summary.append({
            "type": t["type"],
            "title": t["title"],
            "icon": t["icon"],
            "objectifs": objectifs,
        })

    tools_json = json.dumps(tools_summary, ensure_ascii=False, indent=2)
    prenom = profile.get("prenom", "l'utilisateur")
    activite = profile.get("activite", "son activité")

    system_prompt = (
        "Tu es un assistant qui présente des outils à un utilisateur.\n"
        "Tu dois générer une description COURTE (2 phrases max, ~30 mots) pour chaque outil.\n"
        "La description doit être personnalisée selon le profil et les objectifs couverts.\n"
        "Tutoie l'utilisateur. Sois enthousiaste mais concis.\n"
        "Réponds UNIQUEMENT en JSON valide, sans markdown ni texte autour.\n\n"
        "Format attendu :\n"
        '{"descriptions": [{"type": "crm", "description": "..."}, ...]}'
    )

    prompt = (
        f"L'utilisateur s'appelle {prenom} et fait : {activite}.\n\n"
        f"Voici les outils à présenter :\n{tools_json}\n\n"
        f"Génère une description courte et personnalisée pour chaque outil."
    )

    agent = Agent(
        name="tool_describer",
        model=make_model(MODEL_8B, max_tokens=10000),
        system_prompt=system_prompt,
        callback_handler=None,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        result = agent(prompt)
        result_text = str(result)
        try:
            parsed = parse_and_validate(result_text, ToolDescriptionsResult)
            # Fusionner avec les infos originales (title, icon)
            desc_by_type = {d.type: d.description for d in parsed.descriptions}
            enriched = []
            for t in tools:
                enriched.append({
                    "type": t["type"],
                    "title": t["title"],
                    "icon": t["icon"],
                    "description": desc_by_type.get(t["type"], ""),
                })
            return enriched
        except (ValueError, Exception) as e:
            logger.warning("Tool descriptions — tentative %d/%d: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                prompt = (
                    f"Ta réponse précédente n'est pas un JSON valide.\n"
                    f"Erreur: {e}\n\n"
                    f"Renvoie UNIQUEMENT le JSON corrigé."
                )
            else:
                logger.error("Échec génération descriptions après %d tentatives", MAX_RETRIES)
                # Fallback : descriptions vides
                return [
                    {"type": t["type"], "title": t["title"], "icon": t["icon"], "description": ""}
                    for t in tools
                ]


# ─── Main ─────────────────────────────────────────────────────────────

def run(profile_path: Path):
    logger.info("Chargement du profil: %s", profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    # Init DB
    db.init_db()

    print("\n" + "=" * 60)
    print("  WORKFLOW ONBOARDING — Mode séquentiel")
    print("=" * 60)
    print(f"  Profil: {profile.get('prenom')} — {profile.get('activite', '?')}")
    print("=" * 60 + "\n")

    # ── Étape 1 : Analyse ──
    analyse = step_analyse(profile)

    print("\n" + "─" * 60)
    print("  RÉSULTAT — Analyse & Objectifs priorisés")
    print("─" * 60)
    print(f"\n  Situation: {analyse.analyse_situation}\n")

    for obj in analyse.objectifs:
        print(f"  #{obj.rang}  {obj.objectif}")
        print(f"       Urgence: {obj.urgence} | Impact: {obj.impact}")
        print(f"       {obj.justification}")
        print()

    # Sauvegarde fichier step 1
    output_dir = profile_path.resolve().parent
    (output_dir / "step1_analyse.json").write_text(
        analyse.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info("Step 1 sauvegardé: %s", output_dir / "step1_analyse.json")

    # ── Étape 2 : Mapping des outils ──
    tool_mapping = step_map_tools(profile, analyse)

    print("\n" + "─" * 60)
    print("  RÉSULTAT — Mapping Objectifs → Outils")
    print("─" * 60 + "\n")

    for a in tool_mapping.assignations:
        print(f"  #{a.rang}  {a.objectif}")
        print(f"       Outil: {a.tool_type} — {a.raison}")
        print()

    print("  " + "─" * 56)
    print("  DASHBOARD — Outils à activer\n")
    for t in tool_mapping.outils_dashboard:
        objectifs_str = ", ".join(f"#{r}" for r in t.couvre_objectifs)
        print(f"  {t.icon}  {t.title} ({t.tool_type})")
        print(f"       Couvre: {objectifs_str}")
        print()

    # Sauvegarde fichier step 2
    (output_dir / "step2_tool_mapping.json").write_text(
        tool_mapping.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info("Step 2 sauvegardé: %s", output_dir / "step2_tool_mapping.json")

    # ── Persistance DB ──
    ids = _merge_and_persist(analyse, tool_mapping)

    # Vérification
    saved = db.load_objectifs()
    print("─" * 60)
    print(f"  DB — {len(saved)} objectifs persistés")
    print("─" * 60)
    for o in saved:
        print(f"  id={o['id']}  #{o['rang']}  {o['objectif']}")
        print(f"       {o['tool_type'] or '-'} | {o['statut']}")
    print()

    return {"analyse": analyse, "tool_mapping": tool_mapping}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workflow onboarding séquentiel")
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="Chemin vers le profil JSON",
    )
    args = parser.parse_args()

    if not args.profile.exists():
        logger.error("Profil introuvable: %s", args.profile)
        sys.exit(1)

    run(args.profile)
