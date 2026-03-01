"""
Tool Strands — gestion CRM (clients, factures, relances).
"""
import json
import logging
from datetime import date

from strands import tool

from backend.session import db

logger = logging.getLogger("kameleon.tools.crm")


@tool(name="manage_crm")
def manage_crm(
    session_id: str,
    action: str,
    item_id: int = 0,
    data: str = "{}",
) -> str:
    """Gère le CRM : clients, factures et relances.

    Args:
        session_id: ID de la session utilisateur
        action: "list_clients", "list_factures", "get_facture", "update_facture",
                "analyze_overdue", "save_reminder", "mark_reminder_sent", "list_reminders",
                "get_reminder", "delete_reminder", "update_reminder"
        item_id: ID entier de l'élément (facture, relance) selon l'action
        data: JSON complémentaire. Pour get_facture : {"numero": "FAC-2026-004"} si on n'a pas l'id entier.
              Pour save_reminder : {"facture_id": int, "client_id": int, "objet": str, "corps": str}
    """
    logger.info(">>> manage_crm CALLED — action=%s, session_id=%s, item_id=%s", action, session_id, item_id)

    if action == "list_clients":
        crm = db.load_crm_data(session_id)
        return json.dumps(crm["clients"], ensure_ascii=False)

    elif action == "list_factures":
        crm = db.load_crm_data(session_id)
        # Enrichir avec le nom du client (comme analyze_overdue)
        client_map = {c["id"]: c["nom"] for c in crm["clients"]}
        for f in crm["factures"]:
            f["client_nom"] = client_map.get(f.get("client_id"), "Inconnu")
        return json.dumps(crm["factures"], ensure_ascii=False)

    elif action == "get_facture":
        # Accepte item_id (entier) OU numero (str ex: "FAC-2026-004") dans data
        crm = db.load_crm_data(session_id)
        try:
            extra = json.loads(data)
        except json.JSONDecodeError:
            extra = {}
        numero = extra.get("numero", "")

        facture = None
        if item_id:
            facture = next((f for f in crm["factures"] if f["id"] == item_id), None)
        if facture is None and numero:
            facture = next((f for f in crm["factures"] if f.get("numero") == numero), None)
        # Fallback : si item_id ressemble à un numéro de facture (0 en int), chercher par numéro
        if facture is None and not item_id and not numero:
            return "Erreur : item_id ou data.numero requis pour get_facture"
        if facture is None:
            return f"Erreur : facture introuvable (id={item_id}, numero={numero})"
        return json.dumps(facture, ensure_ascii=False)

    elif action == "update_facture":
        if not item_id:
            return "Erreur : item_id requis pour update_facture"
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        allowed = {"statut", "montant", "date_echeance", "description"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return "Erreur : aucun champ valide à modifier"
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [item_id, session_id]
        with db._connect() as conn:
            cursor = conn.execute(
                f"UPDATE crm_factures SET {set_clause} WHERE id = ? AND session_id = ?",
                values,
            )
            conn.commit()
        if cursor.rowcount > 0:
            return f"Facture {item_id} mise à jour"
        return f"Erreur : facture {item_id} introuvable"

    elif action == "analyze_overdue":
        crm = db.load_crm_data(session_id)
        today = date.today().isoformat()
        overdue = [
            f for f in crm["factures"]
            if f.get("date_echeance") and f["date_echeance"] < today and f.get("statut") != "payee"
        ]
        # Enrichir avec le nom du client
        client_map = {c["id"]: c["nom"] for c in crm["clients"]}
        for f in overdue:
            f["client_nom"] = client_map.get(f.get("client_id"), "Inconnu")
        return json.dumps(overdue, ensure_ascii=False)

    elif action == "save_reminder":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        required = ["facture_id", "client_id", "objet", "corps"]
        missing = [k for k in required if k not in fields]
        if missing:
            return f"Erreur : champs requis manquants : {', '.join(missing)}"
        relance_id = db.save_relance(
            session_id=session_id,
            facture_id=fields["facture_id"],
            client_id=fields["client_id"],
            objet=fields["objet"],
            corps=fields["corps"],
        )
        return f"Relance créée avec id={relance_id}"

    elif action == "mark_reminder_sent":
        if not item_id:
            return "Erreur : item_id requis pour mark_reminder_sent"
        ok = db.mark_relance_sent(item_id)
        if ok:
            return f"Relance {item_id} marquée comme envoyée"
        return f"Erreur : relance {item_id} introuvable ou déjà envoyée"

    elif action == "list_reminders":
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            fields = {}
        facture_id = fields.get("facture_id") or (item_id if item_id else None)
        relances = db.load_relances(session_id, facture_id=facture_id)
        return json.dumps(relances, ensure_ascii=False)

    elif action == "get_reminder":
        if not item_id:
            return "Erreur : item_id requis pour get_reminder"
        relance = db.get_relance(item_id)
        if relance is None:
            return f"Erreur : relance {item_id} introuvable"
        return json.dumps(relance, ensure_ascii=False)

    elif action == "delete_reminder":
        if not item_id:
            return "Erreur : item_id requis pour delete_reminder"
        ok = db.delete_relance(item_id)
        if ok:
            return f"Brouillon de relance {item_id} supprimé"
        return f"Erreur : relance {item_id} introuvable ou déjà envoyée (seuls les brouillons peuvent être supprimés)"

    elif action == "update_reminder":
        if not item_id:
            return "Erreur : item_id requis pour update_reminder"
        try:
            fields = json.loads(data)
        except json.JSONDecodeError:
            return "Erreur : data n'est pas du JSON valide"
        ok = db.update_relance(item_id, objet=fields.get("objet"), corps=fields.get("corps"))
        if ok:
            updated = db.get_relance(item_id)
            return f"Relance {item_id} mise à jour. " + json.dumps(updated, ensure_ascii=False)
        return f"Erreur : relance {item_id} introuvable ou déjà envoyée"

    else:
        return (
            f"Erreur : action '{action}' invalide. Actions : list_clients, list_factures, "
            "get_facture, update_facture, analyze_overdue, save_reminder, mark_reminder_sent, "
            "list_reminders, get_reminder, delete_reminder, update_reminder"
        )
