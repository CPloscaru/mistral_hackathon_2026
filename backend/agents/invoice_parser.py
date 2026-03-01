"""
Agent Mistral 8B spécialisé dans le parsing de factures JSON brutes.
Normalise les données client + facture pour le CRM.
"""
import json
import logging

from strands import Agent

from backend.config import MODEL_8B, make_model

logger = logging.getLogger("kameleon.invoice_parser")

INVOICE_PARSER_PROMPT = """Tu es un agent spécialisé dans le parsing et la normalisation de factures.

Tu reçois un JSON brut contenant une ou plusieurs factures. Tu dois extraire et normaliser les données.

=== FORMAT DE SORTIE ===

Tu DOIS retourner UNIQUEMENT un JSON valide entre balises <parsed_json> et </parsed_json>.

Le JSON doit avoir cette structure :
{
  "clients": [
    {
      "nom": "Nom du client",
      "email": "email@client.fr",
      "telephone": null,
      "secteur": "Secteur d'activité déduit",
      "notes": null
    }
  ],
  "factures": [
    {
      "numero": "FAC-2026-001",
      "client_nom": "Nom du client (pour le matching)",
      "montant": 1800.00,
      "devise": "EUR",
      "date_emission": "2026-01-15",
      "date_echeance": "2026-01-30",
      "statut": "payee",
      "description": "Description courte",
      "items": [
        {"description": "Ligne de facture", "quantite": 1, "prix_unitaire": 1800.00}
      ]
    }
  ]
}

=== RÈGLES ===
- Déduplique les clients (même nom = même client)
- Normalise les statuts en : "payee", "en_attente", "en_retard"
- Si un champ est manquant, utilise null
- Les montants doivent être des nombres (pas de string)
- Les dates au format YYYY-MM-DD
- Devise par défaut : EUR
- Pas de texte avant ni après le bloc JSON
"""


def parse_invoices(raw_json: str) -> dict:
    """
    Parse des factures JSON brutes via l'agent Mistral 8B.

    Args:
        raw_json: JSON string contenant les factures brutes

    Returns:
        Dict avec "clients" et "factures" normalisés
    """
    model = make_model(MODEL_8B, max_tokens=4096)

    agent = Agent(
        model=model,
        system_prompt=INVOICE_PARSER_PROMPT,
    )

    message = f"Voici les factures à parser :\n\n{raw_json}"
    result = agent(message)
    response_text = str(result)

    # Extraire le JSON entre balises
    import re
    match = re.search(r"<parsed_json>\s*(\{.*\})\s*</parsed_json>", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.error("Failed to parse agent JSON output")

    # Fallback : chercher un JSON brut
    match = re.search(r"(\{.*\})", response_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "clients" in data or "factures" in data:
                return data
        except json.JSONDecodeError:
            pass

    logger.error("Invoice parser returned no valid JSON: %s", response_text[:200])
    return {"clients": [], "factures": []}
