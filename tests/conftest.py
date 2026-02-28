"""
Configuration des fixtures partagées pour la suite de tests Kameleon.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Client de test FastAPI synchrone pour l'application Kameleon."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def lea_headers():
    """En-têtes HTTP simulant le sous-domaine de Léa (freelance)."""
    return {"host": "lea.localhost:8000"}


@pytest.fixture
def marc_headers():
    """En-têtes HTTP simulant le sous-domaine de Marc (merchant)."""
    return {"host": "marc.localhost:8000"}


@pytest.fixture
def sophie_headers():
    """En-têtes HTTP simulant le sous-domaine de Sophie (creator)."""
    return {"host": "sophie.localhost:8000"}
