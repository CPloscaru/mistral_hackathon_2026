"""
Middleware FastAPI pour extraire la persona depuis le sous-domaine Host.
Analyse l'en-tête Host et injecte le type de persona dans request.state.
"""
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import SUBDOMAIN_MAP


class SubdomainMiddleware(BaseHTTPMiddleware):
    """
    Extrait le sous-domaine depuis l'en-tête Host et résout la persona correspondante.

    Exemples :
        Host: marc.localhost:8000 -> persona="merchant",  subdomain="marc"
        Host: sophie.localhost:8000 -> persona="creator", subdomain="sophie"
        Host: unknown.localhost   -> persona="creator",   subdomain="unknown"
    """

    async def dispatch(self, request, call_next):
        # Récupère l'en-tête Host (ex: "marc.localhost:8000")
        host = request.headers.get("host", "")

        # Supprime le port si présent (ex: "marc.localhost:8000" -> "marc.localhost")
        host_without_port = host.split(":")[0]

        # Extrait le premier segment comme sous-domaine (ex: "marc")
        parts = host_without_port.split(".")
        subdomain = parts[0].lower() if len(parts) > 1 else ""

        # Résolution de la persona depuis la map, défaut = "creator" (Sophie)
        persona = SUBDOMAIN_MAP.get(subdomain, "creator")

        # Injection dans le state de la requête
        request.state.persona = persona
        request.state.subdomain = subdomain

        response = await call_next(request)
        return response
