"""
Tests d'injection du ton de persona dans les prompts système.
Vérifie que chaque persona produit des prompts avec le ton et le style attendus.
Aucun appel à l'API Mistral — tests structurels sur les chaînes de texte.
"""
import pytest
from backend.agents.prompts import (
    build_system_prompt,
    build_coordinator_prompt,
    PERSONA_TONES,
)


def test_prompt_creator_contient_ton_fun():
    """Le prompt pour la persona 'creator' doit contenir des indicateurs de ton fun/créatif."""
    prompt = build_system_prompt("clients", "creator", {})
    ton = PERSONA_TONES["creator"]
    # Le ton doit contenir les mots clés attendus pour Sophie
    assert "fun" in ton.lower() or "créatif" in ton.lower(), (
        "La tonalité creator doit mentionner 'fun' ou 'créatif'"
    )
    assert "emojis" in ton.lower(), "La tonalité creator doit mentionner les emojis"
    assert ton in prompt, "Le ton creator doit être injecté dans le prompt"


def test_prompt_merchant_contient_ton_direct():
    """Le prompt pour la persona 'merchant' doit contenir des indicateurs de ton chaleureux/direct."""
    prompt = build_system_prompt("finances", "merchant", {})
    ton = PERSONA_TONES["merchant"]
    # Le ton doit contenir les mots clés attendus pour Marc
    assert "chaleureux" in ton.lower(), "La tonalité merchant doit mentionner 'chaleureux'"
    assert "direct" in ton.lower(), "La tonalité merchant doit mentionner 'direct'"
    assert "pratique" in ton.lower(), "La tonalité merchant doit mentionner 'pratique'"
    assert ton in prompt, "Le ton merchant doit être injecté dans le prompt"


def test_prompt_contient_tutoiement():
    """Tous les prompts doivent contenir une instruction de tutoiement."""
    personas = ["creator", "merchant"]
    agents = ["clients", "finances", "planning", "creation", "activite"]

    for persona in personas:
        for agent in agents:
            prompt = build_system_prompt(agent, persona, {})
            assert "tutoie" in prompt.lower() or "tutoies" in prompt.lower(), (
                f"Le prompt agent='{agent}' persona='{persona}' doit contenir une instruction de tutoiement"
            )


def test_prompt_contient_francais():
    """Tous les prompts doivent contenir une instruction de réponse en français."""
    personas = ["creator", "merchant"]
    agents = ["clients", "finances", "planning"]

    for persona in personas:
        for agent in agents:
            prompt = build_system_prompt(agent, persona, {})
            assert "français" in prompt.lower() or "francais" in prompt.lower(), (
                f"Le prompt agent='{agent}' persona='{persona}' doit contenir une instruction en français"
            )


def test_prompt_clients_contient_seed_data():
    """Le prompt de l'agent clients avec seed data doit inclure les informations client."""
    seed_data = {
        "clients": [
            {
                "id": "cli-001",
                "nom": "Marie Dubois",
                "entreprise": "Atelier Dubois",
                "statut": "actif",
            }
        ]
    }
    prompt = build_system_prompt("clients", "merchant", seed_data)
    assert "Marie Dubois" in prompt, (
        "Le prompt clients doit inclure le nom des clients du seed data"
    )
    assert "Atelier Dubois" in prompt, (
        "Le prompt clients doit inclure le nom de l'entreprise du seed data"
    )


def test_prompt_coordinator_contient_routing():
    """Le prompt du coordinateur doit contenir des instructions de routage vers les agents."""
    for persona in ("creator", "merchant"):
        prompt = build_coordinator_prompt(persona, {})
        # Le coordinateur doit mentionner handoff_to_agent pour le routage
        assert "handoff_to_agent" in prompt, (
            f"Le prompt coordinateur (persona='{persona}') doit contenir 'handoff_to_agent'"
        )
        # Le coordinateur ne doit jamais répondre directement
        assert "TOUJOURS" in prompt, (
            f"Le prompt coordinateur (persona='{persona}') doit insister sur le routage"
        )
