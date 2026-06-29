"""Webhook notifications pour Vercel."""

import asyncio
import json
from datetime import datetime
from uuid import UUID

import httpx

from app.config import settings


async def notify_new_email(
    email_id: UUID,
    from_address: str,
    subject: str | None,
    received_at: datetime,
) -> bool:
    """
    Envoie une notification webhook à Vercel quand un nouvel email arrive.
    Retourne True si succès, False sinon.
    """
    if not settings.vercel_webhook_url:
        return False

    payload = {
        "event": "new_email",
        "email_id": str(email_id),
        "from_address": from_address,
        "subject": subject,
        "received_at": received_at.isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.vercel_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            return response.status_code in (200, 201, 202, 204)
    except Exception as exc:
        print(f"Webhook notification failed: {exc}")
        return False


async def notify_email_processed(
    email_id: UUID,
    quote_id: UUID,
    numero_offre: str,
) -> bool:
    """
    Envoie une notification webhook quand un email a été traité par l'IA.
    """
    if not settings.vercel_webhook_url:
        return False

    payload = {
        "event": "email_processed",
        "email_id": str(email_id),
        "quote_id": str(quote_id),
        "numero_offre": numero_offre,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.vercel_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            return response.status_code in (200, 201, 202, 204)
    except Exception as exc:
        print(f"Webhook notification failed: {exc}")
        return False

