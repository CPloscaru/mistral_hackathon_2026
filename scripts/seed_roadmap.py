"""
Script de seed — insère 4 phases roadmap réalistes pour la session existante.
Profil : Marc, designer graphique en transition freelance (6 mois).
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.session import db

SESSION_ID = "bb120635-7d9e-4ebc-a342-eea1f1f200af"

OBJECTIF_SMART = (
    "Lancer mon activité de designer graphique freelance d'ici 6 mois, "
    "avec 3 clients récurrents et un revenu mensuel de 3 000 € minimum."
)

PHASES = [
    {
        "titre": "Mois 1 — Fondations administratives",
        "objectif": "Créer le statut juridique, ouvrir le compte pro et sécuriser les bases légales.",
        "actions": [
            "Inscription micro-entreprise (URSSAF)",
            "Ouverture d'un compte bancaire professionnel",
            "Souscription assurance RC Pro",
            "Rédaction des CGV et mentions légales",
        ],
        "statut": "current",
    },
    {
        "titre": "Mois 2 — Portfolio & présence en ligne",
        "objectif": "Construire un portfolio professionnel et établir une présence digitale crédible.",
        "actions": [
            "Sélection et mise en page de 8-10 projets clés",
            "Création du site portfolio (Webflow / Framer)",
            "Profils LinkedIn et Behance optimisés",
            "Définition de la grille tarifaire",
        ],
        "statut": "future",
    },
    {
        "titre": "Mois 3-4 — Prospection & premiers clients",
        "objectif": "Décrocher les 3 premiers contrats et valider le positionnement tarifaire.",
        "actions": [
            "Identifier 20 prospects dans le secteur cible",
            "Campagne de prospection (emails + LinkedIn)",
            "Réponse à 5 appels d'offres sur Malt / Crème de la Crème",
            "Mise en place d'un template de devis/facture",
        ],
        "statut": "future",
    },
    {
        "titre": "Mois 5-6 — Stabilisation & croissance",
        "objectif": "Atteindre 3 clients récurrents et un revenu mensuel stable de 3 000 €.",
        "actions": [
            "Fidéliser les premiers clients avec un suivi proactif",
            "Mettre en place un système de recommandation",
            "Automatiser la facturation et le suivi des paiements",
            "Bilan financier et ajustement de la stratégie",
        ],
        "statut": "future",
    },
]


def main():
    db.init_db()

    # 1. Insérer les phases roadmap
    db.save_roadmap(SESSION_ID, PHASES, OBJECTIF_SMART)
    print(f"✓ {len(PHASES)} phases roadmap insérées pour session {SESSION_ID}")

    # 2. Vérifier
    roadmap = db.load_roadmap(SESSION_ID)
    print(f"  → {len(roadmap['phases'])} phases en DB")
    print(f"  → Objectif SMART : {roadmap['objectif_smart'][:80]}...")

    # 3. Ajouter le composant roadmap dans active_components si absent
    session = db.load_session(SESSION_ID)
    if session is None:
        print(f"⚠ Session {SESSION_ID} introuvable — seed roadmap OK mais pas d'update active_components")
        return

    components = session.get("active_components", [])
    has_roadmap = any(c.get("type") == "roadmap" for c in components)

    if not has_roadmap:
        components.append({
            "action": "activate",
            "type": "roadmap",
            "id": "roadmap-1",
            "title": "Ma Roadmap",
            "icon": "🗺️",
            "data": None,
        })
        db.save_session(
            session_id=SESSION_ID,
            persona=session["persona"],
            assistant_name=session["assistant_name"],
            maturity_level=session["maturity_level"],
            onboarding_data=session["onboarding_data"],
            active_components=components,
        )
        print("✓ Composant 'roadmap' ajouté dans active_components")
    else:
        print("ℹ Composant 'roadmap' déjà présent dans active_components")


if __name__ == "__main__":
    main()
