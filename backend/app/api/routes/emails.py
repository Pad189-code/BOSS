from uuid import UUID

import json

from fastapi import APIRouter, HTTPException, Query

from app.agents.quote_agent import QuoteAgentDeps, process_email_into_quote
from app.db import get_pool
from app.models.email import EmailProcessResult, EmailRequestSummary, EmailSyncResult
from app.services.email_ingestion import sync_inbox, test_imap_connection
from app.services.quote_mappers import (
    dashboard_line_to_db_fields,
    generate_numero_offre,
    offer_to_agent_metadata,
    quote_line_to_dashboard,
)
from app.services.webhook import notify_email_processed

router = APIRouter(prefix="/emails", tags=["Réception mail"])


@router.get("/config")
async def get_mail_config() -> dict[str, str | bool]:
    from app.config import settings

    return {
        "enabled": settings.mail_enabled,
        "provider": settings.mail_provider,
        "inbox_address": settings.mail_inbox_address or settings.mail_imap_user or "",
        "imap_host": settings.mail_imap_host,
        "imap_user": settings.mail_imap_user or "",
    }


@router.get("/test-connection")
async def mail_test_connection() -> dict[str, str]:
    try:
        return await test_imap_connection()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync", response_model=EmailSyncResult)
async def sync_mailbox(
    limit: int | None = Query(default=None, ge=1, le=50),
) -> EmailSyncResult:
    """Lit la boîte IMAP (Gmail test) et importe les mails non lus."""
    try:
        return await sync_inbox(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[EmailRequestSummary])
async def list_emails(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EmailRequestSummary]:
    pool = await get_pool()
    filter_sql = ""
    args: list = [limit]
    if status:
        filter_sql = " AND status = $2"
        args = [limit, status]

    rows = await pool.fetch(
        f"""
        SELECT id, external_id, provider::text, from_address, subject,
               body_text, received_at, status::text
        FROM email_requests
        WHERE TRUE {filter_sql}
        ORDER BY received_at DESC
        LIMIT $1
        """,
        *args,
    )
    return [
        EmailRequestSummary(
            id=row["id"],
            external_id=row["external_id"],
            provider=row["provider"],
            from_address=row["from_address"],
            subject=row["subject"],
            body_preview=(row["body_text"] or "")[:200],
            received_at=row["received_at"],
            status=row["status"],
        )
        for row in rows
    ]


@router.post("/{email_request_id}/process", response_model=EmailProcessResult)
async def process_incoming_email(email_request_id: UUID):
    """Lance l'agent IA sur un mail importé et crée le brouillon d'offre."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, from_address, body_text, status::text
        FROM email_requests WHERE id = $1
        """,
        email_request_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Mail introuvable")

    await pool.execute(
        "UPDATE email_requests SET status = 'processing' WHERE id = $1",
        email_request_id,
    )

    deps = QuoteAgentDeps(
        email_request_id=str(email_request_id),
        customer_email=row["from_address"],
    )

    try:
        offer = await process_email_into_quote(
            row["body_text"],
            deps=deps,
            session_id=str(email_request_id),
        )
    except Exception as exc:
        await pool.execute(
            "UPDATE email_requests SET status = 'error' WHERE id = $1",
            email_request_id,
        )
        raise HTTPException(status_code=500, detail=f"Agent IA : {exc}") from exc

    quote_id = await pool.fetchval(
        """
        INSERT INTO quotes (
            email_request_id, status, client_name, total_amount,
            currency, cover_letter, texte_intro, texte_conclusion, agent_metadata
        ) VALUES ($1, 'pending_validation', $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        email_request_id,
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

    await pool.execute(
        "UPDATE email_requests SET status = 'draft_ready' WHERE id = $1",
        email_request_id,
    )

    # Envoyer notification webhook à Vercel
    await notify_email_processed(
        email_id=email_request_id,
        quote_id=quote_id,
        numero_offre=numero_offre,
    )

    return EmailProcessResult(
        email_request_id=email_request_id,
        quote_id=quote_id,
        numero_offre=numero_offre,
    )

