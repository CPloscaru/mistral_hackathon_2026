"""
Point d'entrée de l'application Kameleon.
Lance le serveur FastAPI avec les routes et middlewares configurés.
"""
from fastapi import FastAPI

app = FastAPI(
    title="Kameleon",
    description="Assistant IA adaptatif pour les indépendants et commerçants",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Endpoint de santé pour vérifier que l'API est opérationnelle."""
    return {"status": "ok", "service": "kameleon"}
