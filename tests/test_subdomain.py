"""
Tests de résolution de la persona depuis le middleware de sous-domaine.
Vérifie que chaque sous-domaine est correctement mappé à sa persona.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_lea_subdomain_resout_freelance():
    """Le sous-domaine 'lea' doit résoudre la persona 'freelance'."""
    response = client.get("/health", headers={"host": "lea.localhost"})
    assert response.status_code == 200
    data = response.json()
    assert data["persona"] == "freelance"


def test_marc_subdomain_resout_merchant():
    """Le sous-domaine 'marc' doit résoudre la persona 'merchant'."""
    response = client.get("/health", headers={"host": "marc.localhost"})
    assert response.status_code == 200
    data = response.json()
    assert data["persona"] == "merchant"


def test_sophie_subdomain_resout_creator():
    """Le sous-domaine 'sophie' doit résoudre la persona 'creator'."""
    response = client.get("/health", headers={"host": "sophie.localhost"})
    assert response.status_code == 200
    data = response.json()
    assert data["persona"] == "creator"


def test_subdomain_inconnu_defaut_creator():
    """Un sous-domaine inconnu doit utiliser la persona par défaut 'creator'."""
    response = client.get("/health", headers={"host": "unknown.localhost"})
    assert response.status_code == 200
    data = response.json()
    assert data["persona"] == "creator"


def test_host_avec_port():
    """Le sous-domaine avec port (lea.localhost:8000) doit résoudre 'freelance'."""
    response = client.get("/health", headers={"host": "lea.localhost:8000"})
    assert response.status_code == 200
    data = response.json()
    assert data["persona"] == "freelance"
