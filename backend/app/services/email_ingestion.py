"""Réception des consultations par IMAP (Gmail / Outlook) — boîte mail de test."""

from __future__ import annotations

import asyncio
import email
import imaplib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from uuid import UUID

from app.config import settings
from app.db import get_pool
from app.models.email import EmailSyncResult
from app.services.webhook import notify_new_email


@dataclass
class ParsedIncomingEmail:
    external_id: str
    from_address: str
    from_name: str | None
    subject: str | None
    body_text: str
    body_html: str | None
    received_at: datetime


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_body(msg: email.message.Message) -> tuple[str, str | None]:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disposition:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if content_type == "text/plain":
                plain_parts.append(decoded.strip())
            elif content_type == "text/html":
                html_parts.append(decoded.strip())
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload is not None:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace").strip()
                if msg.get_content_type() == "text/html":
                    html_parts.append(decoded)
                else:
                    plain_parts.append(decoded)
        except Exception:
            pass

    body_html = html_parts[0] if html_parts else None
    if plain_parts:
        return "\n\n".join(p for p in plain_parts if p), body_html
    if body_html:
        return _html_to_text(body_html), body_html
    return "", None


def _parse_message(raw_bytes: bytes) -> ParsedIncomingEmail:
    msg = email.message_from_bytes(raw_bytes)
    message_id = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
    if not message_id:
        message_id = f"generated-{hash(raw_bytes) & 0xFFFFFFFF:08x}"

    name, addr = parseaddr(_decode_mime_header(msg.get("From")))
    from_address = addr or "inconnu@local"
    from_name = name or None

    subject = _decode_mime_header(msg.get("Subject")) or None
    body_text, body_html = _extract_body(msg)
    if not body_text:
        body_text = "(message vide)"

    date_header = msg.get("Date")
    if date_header:
        try:
            received_at = parsedate_to_datetime(date_header)
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
        except Exception:
            received_at = datetime.now(timezone.utc)
    else:
        received_at = datetime.now(timezone.utc)

    return ParsedIncomingEmail(
        external_id=message_id,
        from_address=from_address,
        from_name=from_name,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        received_at=received_at,
    )


def _normalize_app_password(password: str | None) -> str:
    """Gmail app passwords are 16 chars; Google often displays them with spaces."""
    return (password or "").replace(" ", "").strip()


def _connect_imap() -> imaplib.IMAP4_SSL:
    if not settings.mail_imap_user or not settings.mail_imap_password:
        raise ValueError(
            "MAIL_IMAP_USER et MAIL_IMAP_PASSWORD requis dans .env "
            "(mot de passe d'application Gmail recommandé)"
        )
    client = imaplib.IMAP4_SSL(settings.mail_imap_host, settings.mail_imap_port)
    client.login(settings.mail_imap_user, _normalize_app_password(settings.mail_imap_password))
    return client


def _fetch_recent_messages(*, limit: int) -> list[ParsedIncomingEmail]:
    """Récupère les N derniers mails INBOX (lus ou non) — import dédoublonné en base."""
    client = _connect_imap()
    parsed: list[ParsedIncomingEmail] = []
    try:
        client.select(settings.mail_imap_folder)
        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("Impossible de lister les messages IMAP")

        ids = data[0].split()
        if not ids:
            return []

        for msg_id in ids[-limit:]:
            status, fetched = client.fetch(msg_id, "(RFC822 FLAGS)")
            if status != "OK" or not fetched or not fetched[0]:
                continue
            raw = fetched[0][1]
            if not isinstance(raw, bytes):
                continue
            parsed.append(_parse_message(raw))
            if settings.mail_sync_mark_read:
                flags_raw = fetched[0][0]
                flags = flags_raw.decode() if isinstance(flags_raw, bytes) else str(flags_raw)
                if "\\Seen" not in flags:
                    client.store(msg_id, "+FLAGS", "\\Seen")
    finally:
        try:
            client.logout()
        except Exception:
            pass

    return parsed


async def import_message(pool, message: ParsedIncomingEmail) -> tuple[bool, UUID | None]:
    """
    Insère le mail s'il n'existe pas. 
    Retourne (True, email_id) si importé, (False, None) sinon.
    """
    existing = await pool.fetchval(
        "SELECT id FROM email_requests WHERE external_id = $1",
        message.external_id,
    )
    if existing:
        return False, None

    email_id = await pool.fetchval(
        """
        INSERT INTO email_requests (
            external_id, provider, from_address, subject,
            body_text, body_html, received_at, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'received')
        RETURNING id
        """,
        message.external_id,
        settings.mail_provider,
        message.from_address,
        message.subject,
        message.body_text,
        message.body_html,
        message.received_at,
    )
    return True, email_id


async def sync_inbox(*, limit: int | None = None) -> EmailSyncResult:
    if not settings.mail_enabled:
        raise ValueError("MAIL_ENABLED=false — activez la réception mail dans .env")

    limit = limit or settings.mail_sync_limit
    result = EmailSyncResult()

    try:
        messages = await asyncio.to_thread(_fetch_recent_messages, limit=limit)
    except Exception as exc:
        result.errors.append(str(exc))
        return result

    result.fetched = len(messages)
    pool = await get_pool()

    for message in messages:
        try:
            imported, email_id = await import_message(pool, message)
            if imported and email_id:
                result.imported += 1
                result.message_ids.append(message.external_id)
                # Envoyer notification webhook à Vercel
                await notify_new_email(
                    email_id=email_id,
                    from_address=message.from_address,
                    subject=message.subject,
                    received_at=message.received_at,
                )
            else:
                result.skipped += 1
        except Exception as exc:
            result.errors.append(f"{message.external_id}: {exc}")

    return result


async def test_imap_connection() -> dict[str, str]:
    def _test() -> dict[str, str]:
        client = _connect_imap()
        client.select(settings.mail_imap_folder)
        status, data = client.search(None, "ALL")
        total = len(data[0].split()) if status == "OK" and data[0] else 0
        client.logout()
        return {
            "status": "ok",
            "host": settings.mail_imap_host,
            "user": settings.mail_imap_user or "",
            "folder": settings.mail_imap_folder,
            "messages_in_folder": str(total),
            "inbox_address": settings.mail_inbox_address or settings.mail_imap_user or "",
        }

    return await asyncio.to_thread(_test)

