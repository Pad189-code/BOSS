-- Boss — Schéma PostgreSQL + pgvector
-- Dimension embedding : 1024 (Mistral embed) ou 1536 (OpenAI text-embedding-3-small)
-- Adapter EMBEDDING_DIMENSION dans backend/app/config.py

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Catalogue pièces (40k articles vectorisés)
-- ---------------------------------------------------------------------------
CREATE TABLE catalog_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku             VARCHAR(64) NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    category        VARCHAR(128),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    currency        CHAR(3) NOT NULL DEFAULT 'EUR',
    stock_quantity  INTEGER DEFAULT 0,
    -- Dimension : 1024 (Mistral) ou 1536 (OpenAI) — doit correspondre au modèle d'embedding
    embedding       vector(1024),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN catalog_items.embedding IS
    'Vecteur sémantique (name + description + category) pour recherche pgvector';

-- HNSW : meilleur compromis recall/latence pour ~40k lignes (pas de phase d''entraînement IVFFlat)
CREATE INDEX idx_catalog_items_embedding_hnsw
    ON catalog_items
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_catalog_items_sku ON catalog_items (sku);
CREATE INDEX idx_catalog_items_category ON catalog_items (category);

-- Alternative IVFFlat (si HNSW indisponible sur votre version pgvector) :
-- CREATE INDEX idx_catalog_items_embedding_ivfflat
--     ON catalog_items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 200);
-- ANALYZE catalog_items;

-- ---------------------------------------------------------------------------
-- Demandes mail entrantes
-- ---------------------------------------------------------------------------
CREATE TYPE email_provider AS ENUM ('gmail', 'outlook');
CREATE TYPE request_status AS ENUM (
    'received',
    'processing',
    'draft_ready',
    'validated',
    'sent',
    'error'
);

CREATE TABLE email_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     VARCHAR(255),
    provider        email_provider NOT NULL,
    from_address    VARCHAR(320) NOT NULL,
    subject         TEXT,
    body_text       TEXT NOT NULL,
    body_html       TEXT,
    received_at     TIMESTAMPTZ NOT NULL,
    status          request_status NOT NULL DEFAULT 'received',
    langfuse_trace_id VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_email_requests_status ON email_requests (status);
CREATE INDEX idx_email_requests_received_at ON email_requests (received_at DESC);

-- ---------------------------------------------------------------------------
-- Offres générées par l'agent (validation humaine)
-- ---------------------------------------------------------------------------
CREATE TYPE quote_status AS ENUM ('draft', 'pending_validation', 'validated', 'sent', 'rejected');

CREATE TABLE quotes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_request_id UUID NOT NULL REFERENCES email_requests (id) ON DELETE CASCADE,
    numero_offre    VARCHAR(32),
    status          quote_status NOT NULL DEFAULT 'draft',
    client_name     VARCHAR(255),
    total_amount    NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency        CHAR(3) NOT NULL DEFAULT 'EUR',
    cover_letter    TEXT,
    texte_intro     TEXT,
    texte_conclusion TEXT,
    validated_by    VARCHAR(255),
    validated_at    TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ,
    agent_metadata  JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_quotes_email_request ON quotes (email_request_id);
CREATE INDEX idx_quotes_status ON quotes (status);

-- ---------------------------------------------------------------------------
-- Lignes d'offre (pièces mappées au catalogue)
-- ---------------------------------------------------------------------------
CREATE TABLE quote_line_items (
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

CREATE INDEX idx_quote_line_items_quote ON quote_line_items (quote_id);

-- ---------------------------------------------------------------------------
-- Trigger updated_at
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_catalog_items_updated
    BEFORE UPDATE ON catalog_items
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_email_requests_updated
    BEFORE UPDATE ON email_requests
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_quotes_updated
    BEFORE UPDATE ON quotes
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
