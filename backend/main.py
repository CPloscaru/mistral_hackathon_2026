"""
Point d'entrée de l'application Kameleon.
Lance le serveur FastAPI avec les routes et middlewares configurés.
"""
import logging
import uvicorn

logging.basicConfig(level=logging.INFO)
logging.getLogger("kameleon.swarm").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("strands").setLevel(logging.WARNING)
logging.getLogger("kameleon.swarm").setLevel(logging.INFO)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.middleware.subdomain import SubdomainMiddleware
from backend.routes.chat import router as chat_router
from backend.routes.chat_stream import router as stream_router
from backend.routes.tools import router as tools_router

app = FastAPI(
    title="Kameleon",
    description="Assistant IA adaptatif pour les indépendants et commerçants",
    version="0.1.0",
)

# --- Middlewares ---

# CORS permissif en développement (toutes origines autorisées)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Résolution de la persona depuis le sous-domaine Host
app.add_middleware(SubdomainMiddleware)

# --- Routes ---

app.include_router(chat_router)
app.include_router(stream_router)
app.include_router(tools_router)


@app.get("/health")
async def health_check(request: Request):
    """
    Endpoint de santé — vérifie que l'API est opérationnelle.
    Retourne également la persona résolue depuis le sous-domaine.
    """
    return {
        "status": "ok",
        "service": "kameleon",
        "persona": request.state.persona,
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
