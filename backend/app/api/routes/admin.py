"""Routes d'administration — initialisation de la base de données.

Endpoint :
  POST /api/v1/admin/init-db
    Exécute le schéma SQL complet (extensions, tables, indexes, triggers)
    et les migrations idempotentes.
  
  POST /api/v1/admin/sync-emails
    Synchronise la boîte IMAP et importe les nouveaux emails.
    (Peut être appelé par un cron job)

"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.db import get_pool
from app.models.email import EmailSyncResult
from app.services.email_ingestion import sync_inbox

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Administration"])

# ---------------------------------------------------------------------------
# SQL d'initialisation complet (idempotent — IF NOT EXISTS / OR REPLACE)
# ---------------------------------------------------------------------------

_SQL_EXTENSIONS = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
"""

_SQL_SCHEMA = """
-- ENUMs (ignorés si déjà présents)
DO $$ BEGIN
    CREATE TYPE email_provider AS ENUM ('gmail', 'outlook');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE request_status AS ENUM (
        'received', 'processing', 'draft_ready', 'validated', 'sent', 'error'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE quote_status AS ENUM (
        'draft', 'pending_validation', 'validated', 'sent', 'rejected'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Table : catalog_items
CREATE TABLE IF NOT EXISTS catalog_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku             VARCHAR(64) NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    category        VARCHAR(128),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    currency        CHAR(3) NOT NULL DEFAULT 'EUR',
    stock_quantity  INTEGER DEFAULT 0,
    embedding       vector(1024),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table : email_requests
CREATE TABLE IF NOT EXISTS email_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id         VARCHAR(255),
    provider            email_provider NOT NULL,
    from_address        VARCHAR(320) NOT NULL,
    subject             TEXT,
    body_text           TEXT NOT NULL,
    body_html           TEXT,
    received_at         TIMESTAMPTZ NOT NULL,
    status              request_status NOT NULL DEFAULT 'received',
    langfuse_trace_id   VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table : quotes
CREATE TABLE IF NOT EXISTS quotes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_request_id    UUID NOT NULL REFERENCES email_requests (id) ON DELETE CASCADE,
    numero_offre        VARCHAR(32),
    status              quote_status NOT NULL DEFAULT 'draft',
    client_name         VARCHAR(255),
    total_amount        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency            CHAR(3) NOT NULL DEFAULT 'EUR',
    cover_letter        TEXT,
    texte_intro         TEXT,
    texte_conclusion    TEXT,
    validated_by        VARCHAR(255),
    validated_at        TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ,
    agent_metadata      JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table : quote_line_items
CREATE TABLE IF NOT EXISTS quote_line_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id            UUID NOT NULL REFERENCES quotes (id) ON DELETE CASCADE,
    catalog_item_id     UUID REFERENCES catalog_items (id),
    client_description  TEXT NOT NULL,
    matched_sku         VARCHAR(64),
    matched_name        TEXT,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price          NUMERIC(12, 2) NOT NULL,
    line_total          NUMERIC(14, 2) NOT NULL,
    similarity_score    REAL,
    conditionnement     INTEGER,
    alliage             VARCHAR(128),
    remise_pct          REAL DEFAULT 0,
    en_stock            BOOLEAN DEFAULT TRUE,
    delai_livraison     VARCHAR(64),
    line_metadata       JSONB DEFAULT '{}',
    sort_order          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_catalog_items_embedding_hnsw
    ON catalog_items
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_catalog_items_sku      ON catalog_items (sku);
CREATE INDEX IF NOT EXISTS idx_catalog_items_category ON catalog_items (category);

CREATE INDEX IF NOT EXISTS idx_email_requests_status      ON email_requests (status);
CREATE INDEX IF NOT EXISTS idx_email_requests_received_at ON email_requests (received_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_requests_external_id
    ON email_requests (external_id)
    WHERE external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quotes_email_request ON quotes (email_request_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status        ON quotes (status);
CREATE INDEX IF NOT EXISTS idx_quotes_numero_offre  ON quotes (numero_offre);

CREATE INDEX IF NOT EXISTS idx_quote_line_items_quote ON quote_line_items (quote_id);

-- Trigger updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    CREATE TRIGGER trg_catalog_items_updated
        BEFORE UPDATE ON catalog_items
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_email_requests_updated
        BEFORE UPDATE ON email_requests
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_quotes_updated
        BEFORE UPDATE ON quotes
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/init-db")
async def init_db() -> dict:
    """Initialise le schéma PostgreSQL + pgvector de manière idempotente.

    Crée les extensions, types ENUM, tables, indexes et triggers s'ils
    n'existent pas encore. Peut être appelé plusieurs fois sans risque.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(_SQL_EXTENSIONS)
                await conn.execute(_SQL_SCHEMA)

            # Vérification post-initialisation
            extensions: list[str] = await conn.fetch(
                "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp')"
            )
            tables: list[str] = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                      'catalog_items', 'email_requests',
                      'quotes', 'quote_line_items'
                  )
                ORDER BY table_name
                """
            )

        ext_names = sorted(r["extname"] for r in extensions)
        table_names = sorted(r["table_name"] for r in tables)

        logger.info("init-db: extensions=%s tables=%s", ext_names, table_names)

        return {
            "status": "success",
            "message": "Base de données initialisée",
            "extensions": ext_names,
            "tables_created": table_names,
        }

    except Exception as exc:
        logger.exception("init-db failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Échec de l'initialisation : {exc}",
        ) from exc


@router.post("/sync-emails", response_model=EmailSyncResult)
async def sync_emails_cron() -> EmailSyncResult:
    """Synchronise la boîte IMAP et importe les nouveaux emails.
    
    Endpoint destiné à être appelé par un cron job (ex: toutes les 5 minutes).
    Récupère les derniers emails de la boîte IMAP et les importe en base.
    
    Retourne un résumé du nombre d'emails importés, ignorés et erreurs.
    """
    try:
        result = await sync_inbox()
        logger.info(
            "sync-emails: fetched=%d imported=%d skipped=%d errors=%d",
            result.fetched,
            result.imported,
            result.skipped,
            len(result.errors),
        )
        return result
    except ValueError as exc:
        logger.error("sync-emails: configuration error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("sync-emails: unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

