"""
Point d'entrée de l'application Kameleon.
Lance le serveur FastAPI avec les routes configurées.
"""
import logging
import logging.handlers
from pathlib import Path
import uvicorn

# --- Logging : stdout + fichier rotatif dans logs/ ---
_log_dir = Path(__file__).resolve().parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)

_fmt = logging.Formatter(
    "%(asctime)s | %(name)-22s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_console = logging.StreamHandler()
_console.setFormatter(_fmt)

_file = logging.handlers.RotatingFileHandler(
    _log_dir / "kameleon.log",
    maxBytes=5 * 1024 * 1024,  # 5 Mo
    backupCount=3,
    encoding="utf-8",
)
_file.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("strands").setLevel(logging.WARNING)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.chat_stream import router as stream_router
from backend.routes.chat_init import router as init_router
from backend.routes.chat_onboarding import router as onboarding_router
from backend.routes.chat_common import router as common_router
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

# --- Routes ---

app.include_router(stream_router)
app.include_router(init_router)
app.include_router(onboarding_router)
app.include_router(common_router)
app.include_router(tools_router)


@app.get("/health")
async def health_check():
    """Endpoint de santé."""
    return {
        "status": "ok",
        "service": "kameleon",
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
