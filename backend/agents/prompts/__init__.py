"""
Templates de prompts système pour les agents Kameleon.
Les textes de prompts sont stockés dans des fichiers .txt séparés dans ce dossier.
"""
from pathlib import Path

_DIR = Path(__file__).parent


def _load(name: str) -> str:
    """Charge un fichier texte de prompt depuis le dossier prompts/."""
    return (_DIR / name).read_text(encoding="utf-8").strip()


# Prompt de l'onboarding conversationnel
ONBOARDING_CONVERSATION_PROMPT = _load("onboarding_conversation.txt")

# Prompts du workflow onboarding séquentiel
WORKFLOW_ANALYST_PROMPT = _load("workflow_analyst.txt")
WORKFLOW_TOOL_MAPPER_PROMPT = _load("workflow_tool_mapper.txt")
WORKFLOW_ROADMAP_PROMPT = _load("workflow_roadmap.txt")
