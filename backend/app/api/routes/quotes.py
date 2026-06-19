from uuid import UUID

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.agents.quote_agent import QuoteAgentDeps, process_email_into_quote
from app.db import get_pool
from app.models.quote import OffreDetail, OffreDocxPayload, OffreSummary, OffreUpdateRequest
from app.services.docx_generator import generate_offre_docx, generate_offre_docx_bytes
from app.services.quote_mappers import (
    dashboard_line_to_db_fields,
    generate_numero_offre,
    offre_detail_from_email_row,
    offre_detail_from_rows,
    offre_summary_from_email_row,
    offre_summary_from_row,
    offer_to_agent_metadata,
    quote_line_to_dashboard,
)

router = APIRouter(prefix="/quotes", tags=["Offres"])


class ProcessEmailRequest(BaseModel):
    email_request_id: UUID
    customer_email: str
    email_body: str


def _ui_statut_filter_sql(statut: str | None) -> tuple[str, list[str]]:
    if not statut or statut == "tous":
        return "", []

    if statut == "brouillon":
        return " AND q.status IN ('draft', 'pending_validation') AND COALESCE(q.agent_metadata->>'ui_statut', '') != 'modifiee'", []
    if statut == "modifiee":
        return " AND q.agent_metadata->>'ui_statut' = 'modifiee'", []
    if statut == "validee":
        return " AND q.status = 'validated'", []
    if statut == "envoyee":
        return " AND q.status = 'sent'", []
    if statut == "refusee":
        return " AND q.status = 'rejected'", []
    return "", []


@router.get("", response_model=list[OffreSummary])
async def list_quotes(statut: str | None = Query(default=None)) -> list[OffreSummary]:
    pool = await get_pool()
    filter_sql, _ = _ui_statut_filter_sql(statut)
    rows = await pool.fetch(
        f"""
        SELECT q.id, q.numero_offre, q.status::text, q.client_name,
               q.total_amount::float8, q.created_at, q.agent_metadata,
               e.from_address, e.subject, e.received_at,
               COUNT(l.id) AS nb_lignes
        FROM quotes q
        JOIN email_requests e ON e.id = q.email_request_id
        LEFT JOIN quote_line_items l ON l.quote_id = q.id
        WHERE TRUE {filter_sql}
        GROUP BY q.id, e.id
        ORDER BY q.created_at DESC
        """,
    )
    summaries = [
        offre_summary_from_row(dict(row), nb_lignes=int(row["nb_lignes"])) for row in rows
    ]

    # Mails reçus sans offre → visibles en « brouillon » dans le dashboard
    if not statut or statut in ("tous", "brouillon"):
        email_rows = await pool.fetch(
            """
            SELECT e.id, e.from_address, e.subject, e.body_text, e.received_at, e.status::text
            FROM email_requests e
            LEFT JOIN quotes q ON q.email_request_id = e.id
            WHERE q.id IS NULL
              AND e.status IN ('received', 'processing', 'error')
            ORDER BY e.received_at DESC
            """,
        )
        summaries.extend(offre_summary_from_email_row(dict(row)) for row in email_rows)

    summaries.sort(key=lambda item: item.recu_le, reverse=True)
    return summaries


@router.get("/{quote_id}", response_model=OffreDetail)
async def get_quote(quote_id: UUID) -> OffreDetail:
    return await _load_offre_detail(quote_id)


async def _load_offre_detail(quote_id: UUID) -> OffreDetail:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT q.id, q.numero_offre, q.email_request_id, q.status::text, q.client_name,
               q.cover_letter, q.texte_intro, q.texte_conclusion,
               q.total_amount::float8, q.currency, q.agent_metadata, q.created_at,
               e.subject, e.body_text, e.from_address, e.received_at,
               e.langfuse_trace_id
        FROM quotes q
        JOIN email_requests e ON e.id = q.email_request_id
        WHERE q.id = $1
        """,
        quote_id,
    )
    if not row:
        email_row = await pool.fetchrow(
            """
            SELECT e.id, e.from_address, e.subject, e.body_text, e.received_at, e.status::text
            FROM email_requests e
            LEFT JOIN quotes q ON q.email_request_id = e.id
            WHERE e.id = $1 AND q.id IS NULL
            """,
            quote_id,
        )
        if email_row:
            return offre_detail_from_email_row(dict(email_row))
        raise HTTPException(status_code=404, detail="Offre introuvable")

    line_rows = await pool.fetch(
        """
        SELECT client_description, matched_sku, matched_name,
               quantity, unit_price::float8, line_total::float8,
               similarity_score::float8, conditionnement, alliage,
               remise_pct::float8, en_stock, delai_livraison
        FROM quote_line_items
        WHERE quote_id = $1
        ORDER BY sort_order
        """,
        quote_id,
    )
    return offre_detail_from_rows(dict(row), [dict(r) for r in line_rows])


@router.post("/generate-document")
async def generate_document(offre: OffreDocxPayload):
    """Génère un DOCX à partir du payload offre (mode démo ou prévisualisation)."""
    try:
        content = generate_offre_docx_bytes(offre)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"{offre.numero_offre.replace('/', '-')}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{quote_id}/document")
async def download_quote_document(quote_id: UUID):
    """Télécharge le DOCX généré pour une offre persistée."""
    offre = await _load_offre_detail(quote_id)
    try:
        content = generate_offre_docx_bytes(offre)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"{offre.numero_offre.replace('/', '-')}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/process")
async def process_email(body: ProcessEmailRequest):
    deps = QuoteAgentDeps(
        email_request_id=str(body.email_request_id),
        customer_email=body.customer_email,
    )
    offer = await process_email_into_quote(
        body.email_body,
        deps=deps,
        session_id=str(body.email_request_id),
    )

    pool = await get_pool()
    quote_id = await pool.fetchval(
        """
        INSERT INTO quotes (
            email_request_id, status, client_name, total_amount,
            currency, cover_letter, texte_intro, texte_conclusion, agent_metadata
        ) VALUES ($1, 'pending_validation', $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        body.email_request_id,
        offer.client_name,
        offer.total_amount,
        offer.currency,
        f"{offer.greeting}\n\n{offer.closing_notes}",
        offer.greeting,
        offer.closing_notes,
        json.dumps(offer_to_agent_metadata(offer)),
    )

    created_at = await pool.fetchval("SELECT created_at FROM quotes WHERE id = $1", quote_id)
    numero_offre = generate_numero_offre(quote_id, created_at)
    await pool.execute("UPDATE quotes SET numero_offre = $1 WHERE id = $2", numero_offre, quote_id)

    for i, line in enumerate(offer.lines):
        fields = dashboard_line_to_db_fields(quote_line_to_dashboard(line))
        await pool.execute(
            """
            INSERT INTO quote_line_items (
                quote_id, client_description, matched_sku, matched_name,
                quantity, unit_price, line_total, similarity_score,
                conditionnement, alliage, remise_pct, en_stock, delai_livraison,
                sort_order
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
            quote_id,
            fields["client_description"],
            fields["matched_sku"],
            fields["matched_name"],
            fields["quantity"],
            fields["unit_price"],
            fields["line_total"],
            fields["similarity_score"],
            fields["conditionnement"],
            fields["alliage"],
            fields["remise_pct"],
            fields["en_stock"],
            fields["delai_livraison"],
            i,
        )

    return {"quote_id": str(quote_id), "numero_offre": numero_offre, "offer": offer}


@router.patch("/{quote_id}")
async def update_quote(quote_id: UUID, body: OffreUpdateRequest):
    pool = await get_pool()

    if body.texte_intro is not None:
        await pool.execute("UPDATE quotes SET texte_intro = $1 WHERE id = $2", body.texte_intro, quote_id)
    if body.texte_conclusion is not None:
        await pool.execute(
            "UPDATE quotes SET texte_conclusion = $1 WHERE id = $2",
            body.texte_conclusion,
            quote_id,
        )

    if body.statut == "modifiee":
        await pool.execute(
            """
            UPDATE quotes
            SET agent_metadata = COALESCE(agent_metadata, '{}'::jsonb) || '{"ui_statut":"modifiee"}'::jsonb
            WHERE id = $1
            """,
            quote_id,
        )

    if body.lignes is not None:
        await pool.execute("DELETE FROM quote_line_items WHERE quote_id = $1", quote_id)
        for i, line in enumerate(body.lignes):
            fields = dashboard_line_to_db_fields(line)
            await pool.execute(
                """
                INSERT INTO quote_line_items (
                    quote_id, client_description, matched_sku, matched_name,
                    quantity, unit_price, line_total, similarity_score,
                    conditionnement, alliage, remise_pct, en_stock, delai_livraison,
                    sort_order
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                quote_id,
                fields["client_description"],
                fields["matched_sku"],
                fields["matched_name"],
                fields["quantity"],
                fields["unit_price"],
                fields["line_total"],
                fields["similarity_score"],
                fields["conditionnement"],
                fields["alliage"],
                fields["remise_pct"],
                fields["en_stock"],
                fields["delai_livraison"],
                i,
            )

        montant_ttc = body.montant_ttc
        if montant_ttc is None and body.montant_ht is not None:
            montant_ttc = round(body.montant_ht * 1.2, 2)
        if montant_ttc is not None:
            await pool.execute(
                "UPDATE quotes SET total_amount = $1 WHERE id = $2",
                montant_ttc,
                quote_id,
            )

    return {"status": "updated"}


@router.post("/{quote_id}/validate-and-send")
async def validate_and_send(quote_id: UUID, validated_by: str = "employe@boss.fr"):
    pool = await get_pool()
    updated = await pool.fetchrow(
        """
        UPDATE quotes
        SET status = 'validated', validated_by = $1, validated_at = NOW(),
            agent_metadata = COALESCE(agent_metadata, '{}'::jsonb) || '{"ui_statut":"validee"}'::jsonb
        WHERE id = $2 AND status IN ('draft', 'pending_validation')
        RETURNING id, email_request_id
        """,
        validated_by,
        quote_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Offre non trouvée ou déjà validée")

    offre = await _load_offre_detail(quote_id)
    docx_path = generate_offre_docx(offre)

    await pool.execute(
        """
        UPDATE quotes SET status = 'sent', sent_at = NOW(),
            agent_metadata = COALESCE(agent_metadata, '{}'::jsonb) || $2::jsonb
        WHERE id = $1
        """,
        quote_id,
        json.dumps({"ui_statut": "envoyee", "docx_filename": docx_path.name}),
    )
    await pool.execute(
        "UPDATE email_requests SET status = 'sent' WHERE id = $1",
        updated["email_request_id"],
    )
    return {
        "status": "sent",
        "quote_id": str(quote_id),
        "docx_filename": docx_path.name,
        "download_url": f"/api/v1/quotes/{quote_id}/document",
    }


@router.post("/{quote_id}/refuser")
async def reject_quote(quote_id: UUID):
    pool = await get_pool()
    updated = await pool.fetchrow(
        """
        UPDATE quotes
        SET status = 'rejected',
            agent_metadata = COALESCE(agent_metadata, '{}'::jsonb) || '{"ui_statut":"refusee"}'::jsonb
        WHERE id = $1 AND status NOT IN ('sent', 'rejected')
        RETURNING id
        """,
        quote_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Offre non trouvée ou déjà traitée")
    return {"status": "rejected", "quote_id": str(quote_id)}
