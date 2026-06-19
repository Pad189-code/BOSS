"""Test local de génération DOCX (sans base de données)."""

from datetime import datetime
from pathlib import Path

from app.models.quote import OffreDocxPayload, QuoteLineItemDashboard
from app.services.docx_generator import generate_offre_docx

if __name__ == "__main__":
    payload = OffreDocxPayload(
        numero_offre="OP-2026-0042",
        expediteur_nom="Atelier Dupont SAS",
        expediteur_email="j.dupont@atelier-dupont.fr",
        sujet="Demande de prix – pièces inox",
        created_at=datetime.now(),
        texte_intro="Madame, Monsieur Dupont,\n\nVeuillez trouver ci-joint notre offre.",
        texte_conclusion="Offre valable 30 jours. Franco de port > 500 € HT.",
        montant_ht=402.0,
        montant_tva=80.4,
        montant_ttc=482.4,
        lignes=[
            QuoteLineItemDashboard(
                reference="959310YH",
                designation="Rondelle plate M24",
                conditionnement=50,
                alliage="Inox A4",
                quantite_boites=5,
                prix_unitaire_ht=40.0,
                remise_pct=0,
                prix_total_ht=200.0,
                en_stock=True,
                delai_livraison="1 semaine",
                score_similarite=0.91,
                description_originale_client="vis hex M10x30 inox",
            ),
            QuoteLineItemDashboard(
                reference="511615MW",
                designation="Écrou hexagonal M20",
                conditionnement=10,
                alliage="Acier zingué",
                quantite_boites=10,
                prix_unitaire_ht=12.28,
                remise_pct=0,
                prix_total_ht=122.8,
                en_stock=True,
                delai_livraison="1 semaine",
                score_similarite=0.88,
                description_originale_client="écrous M12 zingués",
            ),
            QuoteLineItemDashboard(
                reference="908386HR",
                designation="Boulon hexagonal M30x10",
                conditionnement=500,
                alliage="Inox 316",
                quantite_boites=2,
                prix_unitaire_ht=39.6,
                remise_pct=0,
                prix_total_ht=79.2,
                en_stock=True,
                delai_livraison="1 semaine",
                score_similarite=0.86,
                description_originale_client="rondelles M16 inox 316",
            ),
        ],
    )
    path = generate_offre_docx(payload)
    print(f"DOCX genere : {path}")
    print(f"Taille      : {Path(path).stat().st_size} octets")
