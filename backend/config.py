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
COORDINATOR_MODEL = "magistral-medium-2509"
ORCHESTRATOR_MODEL = "mistral-large-2512"
SPECIALIST_MODEL = "magistral-small-2509"
MISTRAL_LARGE = "mistral-large-2512"
MODEL_8B = "ministral-8b-2512"
MODEL_3B = "ministral-3b-2512"
MODEL_14B = "ministral-14b-2512"


def make_model(model_id: str, **kwargs):
    """Retourne le bon wrapper Strands selon le modèle.

    - magistral-* → MagistralModel (gère thinking tokens + content list)
    - ministral-* / autre → MistralModel standard
    """
    if model_id.startswith("magistral"):
        from backend.models.magistral import MagistralModel
        return MagistralModel(model_id=model_id, api_key=MISTRAL_API, **kwargs)
    else:
        from strands.models.mistral import MistralModel
        return MistralModel(model_id=model_id, api_key=MISTRAL_API, **kwargs)

