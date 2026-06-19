"""Mapping entre modèles DB/API et format dashboard employé."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.quote import (
    OffreDetail,
    OffreSummary,
    QuoteLineItem,
    QuoteLineItemDashboard,
    QuoteOffer,
)
from app.models.catalog import CatalogMatch


def db_status_to_ui(status: str, agent_metadata: dict[str, Any] | None = None) -> str:
    metadata = agent_metadata or {}
    if metadata.get("ui_statut"):
        return str(metadata["ui_statut"])

    mapping = {
        "draft": "brouillon",
        "pending_validation": "brouillon",
        "validated": "validee",
        "sent": "envoyee",
        "rejected": "refusee",
    }
    return mapping.get(status, "brouillon")


def ui_status_to_db(statut: str | None) -> str | None:
    if not statut:
        return None
    mapping = {
        "brouillon": "pending_validation",
        "modifiee": "pending_validation",
        "validee": "validated",
        "envoyee": "sent",
        "refusee": "rejected",
    }
    return mapping.get(statut)


def line_item_from_catalog_match(
    part_description: str,
    quantity: int,
    match: CatalogMatch,
    *,
    remise_pct: float = 0,
) -> QuoteLineItem:
    unit_price = match.unit_price
    line_total = round(unit_price * quantity * (1 - remise_pct / 100), 2)
    return QuoteLineItem(
        client_description=part_description,
        catalog_sku=match.sku,
        catalog_name=match.name,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        similarity_score=match.similarity,
        conditionnement=match.conditionnement,
        alliage=match.category,
        remise_pct=remise_pct,
        en_stock=match.en_stock if match.en_stock is not None else True,
        delai_livraison=match.delai_livraison or "1 semaine",
    )


def dashboard_line_from_db(row: dict[str, Any]) -> QuoteLineItemDashboard:
    return QuoteLineItemDashboard(
        reference=row.get("matched_sku") or "",
        designation=row.get("matched_name") or "",
        conditionnement=int(row.get("conditionnement") or 1),
        alliage=row.get("alliage") or "",
        quantite_boites=int(row.get("quantity") or 1),
        prix_unitaire_ht=float(row.get("unit_price") or 0),
        remise_pct=float(row.get("remise_pct") or 0),
        prix_total_ht=float(row.get("line_total") or 0),
        en_stock=bool(row.get("en_stock") if row.get("en_stock") is not None else True),
        delai_livraison=row.get("delai_livraison") or "1 semaine",
        score_similarite=row.get("similarity_score"),
        description_originale_client=row.get("client_description") or "",
    )


def dashboard_line_to_db_fields(line: QuoteLineItemDashboard) -> dict[str, Any]:
    return {
        "client_description": line.description_originale_client,
        "matched_sku": line.reference,
        "matched_name": line.designation,
        "quantity": line.quantite_boites,
        "unit_price": line.prix_unitaire_ht,
        "line_total": line.prix_total_ht,
        "similarity_score": line.score_similarite,
        "conditionnement": line.conditionnement,
        "alliage": line.alliage,
        "remise_pct": line.remise_pct,
        "en_stock": line.en_stock,
        "delai_livraison": line.delai_livraison,
    }


def quote_line_to_dashboard(line: QuoteLineItem) -> QuoteLineItemDashboard:
    return QuoteLineItemDashboard(
        reference=line.catalog_sku,
        designation=line.catalog_name,
        conditionnement=line.conditionnement or 1,
        alliage=line.alliage or "",
        quantite_boites=line.quantity,
        prix_unitaire_ht=line.unit_price,
        remise_pct=line.remise_pct,
        prix_total_ht=line.line_total,
        en_stock=line.en_stock,
        delai_livraison=line.delai_livraison or "1 semaine",
        score_similarite=line.similarity_score,
        description_originale_client=line.client_description,
    )


def compute_totals_from_lines(lines: list[QuoteLineItemDashboard]) -> tuple[float, float, float]:
    ht = round(sum(line.prix_total_ht for line in lines), 2)
    tva = round(ht * 0.2, 2)
    ttc = round(ht + tva, 2)
    return ht, tva, ttc


def generate_numero_offre(quote_id: UUID, created_at: datetime) -> str:
    return f"OP-{created_at.year}-{quote_id.hex[:4].upper()}"


def parse_agent_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def offre_summary_from_email_row(row: dict[str, Any]) -> OffreSummary:
    """Mail importé sans offre générée — visible dans le dashboard."""
    email_id = row["id"]
    received_at = row["received_at"]
    from_address = row.get("from_address") or ""
    local_part = from_address.split("@")[0].replace(".", " ").title()

    return OffreSummary(
        id=email_id,
        numero_offre=f"MAIL-{email_id.hex[:8].upper()}",
        statut="brouillon",
        montant_ht=0,
        montant_tva=0,
        montant_ttc=0,
        expediteur_nom=local_part or "Client",
        expediteur_email=from_address,
        sujet=row.get("subject") or "Demande de prix",
        created_at=received_at,
        recu_le=received_at,
        nb_lignes=0,
    )


def offre_detail_from_email_row(row: dict[str, Any]) -> OffreDetail:
    summary = offre_summary_from_email_row(row)
    body = row.get("body_text") or ""
    return OffreDetail(
        **summary.model_dump(),
        texte_intro="Mail reçu — en attente de traitement par l'agent IA.",
        texte_conclusion="",
        corps_email=body,
        lignes=[],
    )


def offre_summary_from_row(row: dict[str, Any], *, nb_lignes: int) -> OffreSummary:
    agent_metadata = parse_agent_metadata(row.get("agent_metadata"))
    montant_ttc = float(row.get("total_amount") or 0)
    montant_ht = round(montant_ttc / 1.2, 2)
    montant_tva = round(montant_ttc - montant_ht, 2)
    created_at = row["created_at"]
    quote_id = row["id"]

    return OffreSummary(
        id=quote_id,
        numero_offre=row.get("numero_offre") or generate_numero_offre(quote_id, created_at),
        statut=db_status_to_ui(row["status"], agent_metadata),
        montant_ht=montant_ht,
        montant_tva=montant_tva,
        montant_ttc=montant_ttc,
        expediteur_nom=row.get("client_name") or row.get("from_address") or "Client",
        expediteur_email=row.get("from_address") or "",
        sujet=row.get("subject") or "Demande de prix",
        created_at=created_at,
        recu_le=row.get("received_at") or created_at,
        nb_lignes=nb_lignes,
    )


def offre_detail_from_rows(
    quote_row: dict[str, Any],
    line_rows: list[dict[str, Any]],
) -> OffreDetail:
    agent_metadata = parse_agent_metadata(quote_row.get("agent_metadata"))
    lignes = [dashboard_line_from_db(dict(r)) for r in line_rows]
    summary = offre_summary_from_row(quote_row, nb_lignes=len(lignes))

    return OffreDetail(
        **summary.model_dump(),
        texte_intro=quote_row.get("texte_intro")
        or agent_metadata.get("greeting")
        or (quote_row.get("cover_letter") or "").split("\n\n")[0],
        texte_conclusion=quote_row.get("texte_conclusion")
        or agent_metadata.get("closing_notes")
        or "",
        corps_email=quote_row.get("body_text") or "",
        lignes=lignes,
        tokens_utilises=agent_metadata.get("tokens_utilises"),
        cout_usd=agent_metadata.get("cout_usd"),
        latence_ms=agent_metadata.get("latence_ms"),
        langfuse_trace_id=agent_metadata.get("langfuse_trace_id")
        or quote_row.get("langfuse_trace_id"),
    )


def offer_to_agent_metadata(offer: QuoteOffer, **extra: Any) -> dict[str, Any]:
    data = offer.model_dump()
    data.update(extra)
    return data
