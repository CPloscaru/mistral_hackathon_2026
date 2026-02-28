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


# ─── CRM (Clients & Factures) ───

@router.get("/crm")
async def get_crm(session_id: str):
    """Retourne clients et factures d'une session."""
    data = db.load_crm_data(session_id)
    return data


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
