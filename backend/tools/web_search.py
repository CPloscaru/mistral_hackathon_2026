"""
Tool de recherche web via Brave Search API pour les agents Strands.

Utilisé par l'agent Recherche du swarm onboarding pour trouver des informations
à jour sur les réglementations, aides, et conseils pour entrepreneurs français.
"""
import os
import httpx
from strands import tool

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


@tool
def web_search(query: str, num_results: int = 5) -> str:
    """Recherche sur le web via Brave Search. Utilise cet outil pour trouver des informations à jour sur les réglementations, aides, statuts juridiques, ou tout sujet lié à l'entrepreneuriat en France.

    Args:
        query: La requête de recherche en français. Sois précis et inclus "France" ou "français" si pertinent.
        num_results: Nombre de résultats à retourner (entre 1 et 10).
    """
    if not BRAVE_API_KEY:
        return "Erreur : BRAVE_SEARCH_API_KEY non configurée. Recherche web indisponible."

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }

    params = {
        "q": query,
        "count": min(num_results, 10),
        "search_lang": "fr",
        "country": "FR",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return f"Aucun résultat trouvé pour : {query}"

        output_lines = [f"Résultats pour : {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("url", "")
            description = r.get("description", "")
            output_lines.append(f"{i}. **{title}**\n   {url}\n   {description}\n")

        return "\n".join(output_lines)

    except httpx.HTTPStatusError as e:
        return f"Erreur Brave Search (HTTP {e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        return f"Erreur lors de la recherche : {str(e)}"
