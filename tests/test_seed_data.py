"""
Tests d'intégrité des données de seed.
Vérifie la structure, le volume et le contenu des fichiers lea.json et marc.json.
"""
import json
import pytest
from pathlib import Path

# Chemins vers les fichiers de seed
_DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"


@pytest.fixture(scope="module")
def lea_data():
    """Charge les données de seed de Léa."""
    with open(_DATA_DIR / "lea.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def marc_data():
    """Charge les données de seed de Marc."""
    with open(_DATA_DIR / "marc.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_lea_seed_data_structure(lea_data):
    """Le fichier lea.json doit contenir les clés : clients, finances, planning, projets."""
    for cle in ("clients", "finances", "planning", "projets"):
        assert cle in lea_data, f"Clé manquante dans lea.json : {cle}"


def test_marc_seed_data_structure(marc_data):
    """Le fichier marc.json doit contenir les clés : clients, finances, planning, stock."""
    for cle in ("clients", "finances", "planning", "stock"):
        assert cle in marc_data, f"Clé manquante dans marc.json : {cle}"


def test_lea_clients_minimum_15(lea_data):
    """Léa doit avoir au moins 15 clients dans son fichier de seed."""
    assert len(lea_data["clients"]) >= 15


def test_marc_stock_minimum_15(marc_data):
    """Marc doit avoir au moins 15 références de stock dans son fichier de seed."""
    assert len(marc_data["stock"]) >= 15


def test_lea_contenu_en_francais(lea_data):
    """Les noms de clients de Léa doivent être des prénoms/noms français."""
    noms_clients = [c["nom"] for c in lea_data["clients"]]
    # Vérification ponctuelle : au moins quelques noms typiquement français
    noms_francais_attendus = ["Thomas", "Camille", "Baptiste", "Sophie", "Pierre",
                               "Marie", "Julie", "Nicolas", "Claire", "Laurent"]
    correspondances = sum(
        1 for nom in noms_clients
        if any(prenom in nom for prenom in noms_francais_attendus)
    )
    assert correspondances >= 3, (
        f"Trop peu de noms français détectés : {correspondances} sur {len(noms_clients)}"
    )


def test_marc_contenu_en_francais(marc_data):
    """Les noms des produits de Marc doivent être en français."""
    noms_produits = [s["nom"] for s in marc_data["stock"]]
    # Vérification ponctuelle : les noms doivent contenir des mots français
    mots_francais = ["Savon", "Huile", "Coffret", "Shampooing", "Crème",
                     "Provence", "Lavande", "Beurre", "Miel"]
    correspondances = sum(
        1 for nom in noms_produits
        if any(mot in nom for mot in mots_francais)
    )
    assert correspondances >= 5, (
        f"Trop peu de noms de produits français détectés : {correspondances} sur {len(noms_produits)}"
    )


def test_lea_finances_montants_eur(lea_data):
    """Tous les montants financiers de Léa doivent être numériques."""
    for entree in lea_data["finances"]:
        assert isinstance(entree["montant_ht"], (int, float)), (
            f"montant_ht non numérique pour l'entrée {entree.get('id', '?')}"
        )
        assert isinstance(entree["montant_ttc"], (int, float)), (
            f"montant_ttc non numérique pour l'entrée {entree.get('id', '?')}"
        )


def test_marc_finances_montants_eur(marc_data):
    """Tous les montants financiers de Marc doivent être numériques."""
    for entree in marc_data["finances"]:
        assert isinstance(entree["montant_ht"], (int, float)), (
            f"montant_ht non numérique pour l'entrée {entree.get('id', '?')}"
        )
        assert isinstance(entree["montant_ttc"], (int, float)), (
            f"montant_ttc non numérique pour l'entrée {entree.get('id', '?')}"
        )
