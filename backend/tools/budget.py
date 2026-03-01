"""
Tool Strands — gestion du budget prévisionnel.
"""
import json

from strands import tool

from backend.session import db


@tool(name="manage_budget")
def manage_budget(
    session_id: str,
    action: str,
    data: str = "{}",
) -> str:
    """Gère le budget prévisionnel de l'utilisateur.

    Args:
        session_id: ID de la session utilisateur
        action: "get", "add_charge", "remove_charge", "update_revenus", "recalculate", "save"
        data: JSON avec les données selon l'action
    """
    if action == "get":
        budget = db.load_budget_data(session_id)
        if budget is None:
            return "Aucun budget trouvé pour cette session"
        return json.dumps(budget, ensure_ascii=False)

    elif action == "add_charge":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        budget = db.load_budget_data(session_id) or {"charges": [], "revenus": 0, "solde": 0}
        charge = {
            "label": fields.get("label", "Charge"),
            "montant": fields.get("montant", 0),
            "categorie": fields.get("categorie", "autre"),
        }
        budget.setdefault("charges", []).append(charge)
        budget["solde"] = budget.get("revenus", 0) - sum(c.get("montant", 0) for c in budget["charges"])
        db.save_budget_data(session_id, budget)
        return f"Charge '{charge['label']}' ajoutée ({charge['montant']} €)"

    elif action == "remove_charge":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        index = fields.get("index")
        if index is None:
            return "Erreur : 'index' requis pour remove_charge"
        budget = db.load_budget_data(session_id)
        if budget is None:
            return "Aucun budget trouvé"
        charges = budget.get("charges", [])
        if index < 0 or index >= len(charges):
            return f"Erreur : index {index} hors limites (0-{len(charges)-1})"
        removed = charges.pop(index)
        budget["solde"] = budget.get("revenus", 0) - sum(c.get("montant", 0) for c in charges)
        db.save_budget_data(session_id, budget)
        return f"Charge '{removed.get('label')}' supprimée"

    elif action == "update_revenus":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        budget = db.load_budget_data(session_id) or {"charges": [], "revenus": 0, "solde": 0}
        budget["revenus"] = fields.get("revenus", budget.get("revenus", 0))
        budget["solde"] = budget["revenus"] - sum(c.get("montant", 0) for c in budget.get("charges", []))
        db.save_budget_data(session_id, budget)
        return f"Revenus mis à jour : {budget['revenus']} €, solde : {budget['solde']} €"

    elif action == "recalculate":
        budget = db.load_budget_data(session_id)
        if budget is None:
            return "Aucun budget trouvé"
        total_charges = sum(c.get("montant", 0) for c in budget.get("charges", []))
        budget["solde"] = budget.get("revenus", 0) - total_charges
        db.save_budget_data(session_id, budget)
        return json.dumps({"revenus": budget["revenus"], "total_charges": total_charges, "solde": budget["solde"]}, ensure_ascii=False)

    elif action == "save":
        try:
            budget = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        db.save_budget_data(session_id, budget)
        return "Budget sauvegardé"

    else:
        return f"Erreur : action '{action}' invalide. Actions : get, add_charge, remove_charge, update_revenus, recalculate, save"
