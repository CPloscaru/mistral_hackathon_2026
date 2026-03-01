"""
Endpoints REST pour les outils dashboard (Admin Checklist, Calendrier, CRM).
"""
import json
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.session import db

logger = logging.getLogger("kameleon.tools")

router = APIRouter(prefix="/tools")


# ─── Admin Checklist ───

@router.get("/admin-checklist")
async def get_admin_checklist(session_id: str):
    """Retourne la checklist admin d'une session."""
    items = db.load_admin_checklist(session_id)
    return {"items": items}


class ToggleRequest(BaseModel):
    item_id: int


@router.post("/admin-checklist/toggle")
async def toggle_admin_item(body: ToggleRequest):
    """Toggle done/undone pour un item de la checklist admin."""
    new_done = db.toggle_admin_item(body.item_id)
    return {"item_id": body.item_id, "done": new_done}


# ─── Calendar Events ───

@router.get("/calendar")
async def get_calendar(session_id: str):
    """Retourne les events calendrier d'une session."""
    events = db.load_calendar_events(session_id)
    return {"events": events}


# ─── Budget ───

@router.get("/budget")
async def get_budget(session_id: str):
    """Retourne les données budget d'une session (table dédiée, fallback onboarding_data._plan)."""
    # 1. Table dédiée (source de vérité)
    budget_data = db.load_budget_data(session_id)
    if budget_data:
        return {"budget_data": budget_data}

    # 2. Fallback : ancien chemin dans onboarding_data._plan
    record = db.load_session(session_id)
    if record is None:
        return {"error": "Session introuvable"}
    onboarding_data = record.get("onboarding_data") or {}
    plan = onboarding_data.get("_plan") or {}
    tools_data = plan.get("tools_data") or {}
    return {"budget_data": tools_data.get("budget_data")}


# ─── Roadmap ───

@router.get("/roadmap")
async def get_roadmap(session_id: str):
    """Retourne les données roadmap d'une session (DB-first, fallback onboarding_data)."""
    # 1. Table dédiée (source de vérité)
    roadmap = db.load_roadmap(session_id)
    if roadmap["phases"]:
        return roadmap

    # 2. Fallback : ancien chemin dans onboarding_data._plan
    record = db.load_session(session_id)
    if record is None:
        return {"error": "Session introuvable"}
    onboarding_data = record.get("onboarding_data") or {}
    plan = onboarding_data.get("_plan") or {}
    return {
        "phases": plan.get("phases", []),
        "objectif_smart": plan.get("objectif_smart", ""),
        "synthese_profil": plan.get("synthese_profil", ""),
        "prochaines_etapes": plan.get("prochaines_etapes", []),
    }


# ─── Prévisions Financières ───

@router.get("/previsions")
async def get_previsions(session_id: str):
    """Retourne les prévisions financières d'une session."""
    previsions = db.load_previsions(session_id)
    return {"previsions": previsions}


# ─── CRM (Clients & Factures) ───

@router.get("/crm")
async def get_crm(session_id: str):
    """Retourne clients et factures d'une session."""
    data = db.load_crm_data(session_id)
    return data


# ─── Objectifs ───

@router.get("/objectifs")
async def get_objectifs():
    """Retourne tous les objectifs, triés par rang."""
    objectifs = db.load_objectifs()
    return {"objectifs": objectifs}


class ObjectifUpdateRequest(BaseModel):
    objectif: str | None = None
    urgence: str | None = None
    impact: str | None = None
    justification: str | None = None
    tool_type: str | None = None
    raison: str | None = None
    rang: int | None = None
    statut: str | None = None


@router.put("/objectifs/{objectif_id}")
async def update_objectif(objectif_id: int, body: ObjectifUpdateRequest):
    """Met à jour un objectif."""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return {"error": "Aucun champ à modifier"}
    ok = db.update_objectif(objectif_id, **fields)
    if not ok:
        return {"error": f"Objectif {objectif_id} introuvable"}
    return {"ok": True, "objectif": db.get_objectif(objectif_id)}


@router.delete("/objectifs/{objectif_id}")
async def delete_objectif(objectif_id: int):
    """Supprime un objectif."""
    ok = db.delete_objectif(objectif_id)
    if not ok:
        return {"error": f"Objectif {objectif_id} introuvable"}
    return {"ok": True}


# ─── CRM Relances ───

@router.get("/crm/relances")
async def get_relances(session_id: str, facture_id: int | None = None):
    """Retourne les relances d'une session, optionnellement filtrées par facture."""
    relances = db.load_relances(session_id, facture_id=facture_id)
    return {"relances": relances}


@router.post("/crm/relances/{relance_id}/send")
async def send_relance(relance_id: int):
    """Marque une relance comme envoyée."""
    ok = db.mark_relance_sent(relance_id)
    if not ok:
        return {"error": f"Relance {relance_id} introuvable ou déjà envoyée"}
    relance = db.get_relance(relance_id)
    return {"ok": True, "relance": relance}


@router.delete("/crm/relances/{relance_id}")
async def delete_relance(relance_id: int):
    """Supprime un brouillon de relance."""
    ok = db.delete_relance(relance_id)
    if not ok:
        return {"error": f"Relance {relance_id} introuvable ou déjà envoyée"}
    return {"ok": True}


class RelanceUpdateRequest(BaseModel):
    objet: str | None = None
    corps: str | None = None


@router.put("/crm/relances/{relance_id}")
async def update_relance(relance_id: int, body: RelanceUpdateRequest):
    """Met à jour un brouillon de relance."""
    ok = db.update_relance(relance_id, objet=body.objet, corps=body.corps)
    if not ok:
        return {"error": f"Relance {relance_id} introuvable ou déjà envoyée"}
    relance = db.get_relance(relance_id)
    return {"ok": True, "relance": relance}


# ─── CRM Import ───

class ImportRequest(BaseModel):
    session_id: str
    factures: list[dict]


@router.post("/crm/import")
async def import_crm(body: ImportRequest):
    """
    Import de factures JSON brutes.
    Appelle l'agent parser Mistral 8B pour normaliser, puis persiste en DB.
    """
    from backend.agents.invoice_parser import parse_invoices

    raw_json = json.dumps(body.factures, ensure_ascii=False)
    logger.info("Importing %d raw invoices for session %s", len(body.factures), body.session_id)

    # Parse via agent
    parsed = parse_invoices(raw_json)

    # Persister les clients
    client_name_to_id = {}
    for client in parsed.get("clients", []):
        client_id = db.save_crm_client(body.session_id, client)
        client_name_to_id[client.get("nom", "")] = client_id

    # Persister les factures avec link client
    saved_factures = []
    for facture in parsed.get("factures", []):
        client_nom = facture.pop("client_nom", None)
        if client_nom and client_nom in client_name_to_id:
            facture["client_id"] = client_name_to_id[client_nom]
        facture_id = db.save_crm_facture(body.session_id, facture)
        facture["id"] = facture_id
        saved_factures.append(facture)

    logger.info("Imported %d clients, %d factures", len(parsed.get("clients", [])), len(saved_factures))

    # Retourner les données complètes
    return db.load_crm_data(body.session_id)
