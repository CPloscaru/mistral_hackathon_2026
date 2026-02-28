"""
Configuration centrale de Kameleon.
Charge les variables d'environnement et définit les constantes de modèles et de personas.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env à la racine du projet
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Clé API Mistral
MISTRAL_API = os.getenv("MISTRAL_API")

# Identifiants des modèles
COORDINATOR_MODEL = "mistral-large-2512"
MODEL_8B = "ministral-8b-2512"
MODEL_3B = "ministral-3b-2512"
MODEL_14B = "ministral-14b-2512"

# Mapping sous-domaine -> type de persona
SUBDOMAIN_MAP = {
    "sophie": "creator",
    "marc": "merchant",
}

# Descriptions de tonalité par persona (injectées dans les system prompts)
PERSONA_TONES = {
    "creator": {
        "name": "Sophie",
        "style": "inspirant et encourageant",
        "description": (
            "Tu parles à Sophie, une créatrice d'activité qui démarre. "
            "Ton style est inspirant, positif et bienveillant. "
            "Tu l'aides à trouver sa voie et à construire son activité étape par étape. "
            "Tu tutoies toujours Sophie."
        ),
    },
    "merchant": {
        "name": "Marc",
        "style": "chaleureux et pragmatique",
        "description": (
            "Tu parles à Marc, un artisan savonnier qui tient une boutique. "
            "Ton style est chaleureux, simple et pragmatique. "
            "Tu l'aides à gérer ses ventes, son stock, ses clients et son planning. "
            "Tu tutoies toujours Marc."
        ),
    },
}
