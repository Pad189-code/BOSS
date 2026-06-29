-- Boss — Schéma minimal pour le dashboard offres (sans pgvector)
-- Usage Railway : Postgres → Query → coller ce script → Run
--
-- Couvre : emails, offres, lignes + stub catalogue (requis par /health).
-- Ne crée PAS l'extension vector ni les embeddings.
-- Pour la recherche sémantique plus tard : lancer database/schema.sql sur une instance pgvector.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Catalogue (stub — sans colonne embedding)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS catalog_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku             VARCHAR(64) NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    category        VARCHAR(128),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    currency        CHAR(3) NOT NULL DEFAULT 'EUR',
    stock_quantity  INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_catalog_items_sku ON catalog_items (sku);
CREATE INDEX IF NOT EXISTS idx_catalog_items_category ON catalog_items (category);

-- ---------------------------------------------------------------------------
-- Demandes mail
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    CREATE TYPE email_provider AS ENUM ('gmail', 'outlook');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE request_status AS ENUM (
        'received',
        'processing',
        'draft_ready',
        'validated',
        'sent',
        'error'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS email_requests (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id       VARCHAR(255),
    provider          email_provider NOT NULL,
    from_address      VARCHAR(320) NOT NULL,
    subject           TEXT,
    body_text         TEXT NOT NULL,
    body_html         TEXT,
    received_at       TIMESTAMPTZ NOT NULL,
    status            request_status NOT NULL DEFAULT 'received',
    langfuse_trace_id VARCHAR(64),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_requests_status ON email_requests (status);
CREATE INDEX IF NOT EXISTS idx_email_requests_received_at ON email_requests (received_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_requests_external_id
    ON email_requests (external_id)
    WHERE external_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Offres
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    CREATE TYPE quote_status AS ENUM (
        'draft',
        'pending_validation',
        'validated',
        'sent',
        'rejected'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS quotes (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_request_id UUID NOT NULL REFERENCES email_requests (id) ON DELETE CASCADE,
    numero_offre     VARCHAR(32),
    status           quote_status NOT NULL DEFAULT 'draft',
    client_name      VARCHAR(255),
    total_amount     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency         CHAR(3) NOT NULL DEFAULT 'EUR',
    cover_letter     TEXT,
    texte_intro      TEXT,
    texte_conclusion TEXT,
    validated_by     VARCHAR(255),
    validated_at     TIMESTAMPTZ,
    sent_at          TIMESTAMPTZ,
    agent_metadata   JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quotes_email_request ON quotes (email_request_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes (status);
CREATE INDEX IF NOT EXISTS idx_quotes_numero_offre ON quotes (numero_offre);

-- ---------------------------------------------------------------------------
-- Lignes d'offre
-- ---------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_quote_line_items_quote ON quote_line_items (quote_id);

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

DROP TRIGGER IF EXISTS trg_catalog_items_updated ON catalog_items;
CREATE TRIGGER trg_catalog_items_updated
    BEFORE UPDATE ON catalog_items
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_email_requests_updated ON email_requests;
CREATE TRIGGER trg_email_requests_updated
    BEFORE UPDATE ON email_requests
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_quotes_updated ON quotes;
CREATE TRIGGER trg_quotes_updated
    BEFORE UPDATE ON quotes
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- ---------------------------------------------------------------------------
-- Données de démo (1 mail + 1 offre + 3 lignes)
-- Supprimez ce bloc si vous ne voulez pas de données fictives.
-- ---------------------------------------------------------------------------
INSERT INTO email_requests (
    id, external_id, provider, from_address, subject, body_text, received_at, status
) VALUES (
    'a0000000-0000-4000-8000-000000000001',
    'seed-demo-001',
    'gmail',
    'jean.dupont@atelier-dupont.fr',
    'Demande de devis — visserie inox',
    'Bonjour,

Nous souhaitons recevoir un devis pour les pièces suivantes :
- 5 boîtes de vis hexagonales M10x30 inox
- 10 boîtes d''écrous M12 acier zingué
- 2 boîtes de rondelles M16 inox 316

Merci de nous faire parvenir votre meilleure offre.

Cordialement,
Jean Dupont
Atelier Dupont SAS',
    NOW() - INTERVAL '2 hours',
    'draft_ready'
) ON CONFLICT (id) DO NOTHING;

INSERT INTO quotes (
    id,
    email_request_id,
    numero_offre,
    status,
    client_name,
    total_amount,
    texte_intro,
    texte_conclusion,
    agent_metadata,
    created_at
) VALUES (
    'b0000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'OP-2026-B000',
    'pending_validation',
    'Atelier Dupont SAS',
    1847.40,
    'Madame, Monsieur,',
    'Nous restons à votre disposition pour toute information complémentaire. Cordialement, L''équipe BOSS.',
    '{"ui_statut":"brouillon","tokens_utilises":1240,"cout_usd":0.02,"latence_ms":3200}'::jsonb,
    NOW() - INTERVAL '1 hour'
) ON CONFLICT (id) DO NOTHING;

INSERT INTO quote_line_items (
    id, quote_id, client_description, matched_sku, matched_name,
    quantity, unit_price, line_total, similarity_score,
    conditionnement, alliage, remise_pct, en_stock, delai_livraison, sort_order
) VALUES
(
    'c0000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    '5 boîtes de vis hexagonales M10x30 inox',
    '959310YH',
    'Vis hexagonale M10x30 inox A2',
    5, 42.50, 212.50, 0.94,
    100, 'Inox A2', 0, TRUE, 'En stock', 0
),
(
    'c0000000-0000-4000-8000-000000000002',
    'b0000000-0000-4000-8000-000000000001',
    '10 boîtes d''écrous M12 acier zingué',
    '511615MW',
    'Écrou hexagonal M12 acier zingué',
    10, 28.00, 280.00, 0.91,
    50, 'Acier zingué', 0, TRUE, 'En stock', 1
),
(
    'c0000000-0000-4000-8000-000000000003',
    'b0000000-0000-4000-8000-000000000001',
    '2 boîtes de rondelles M16 inox 316',
    '908386HR',
    'Rondelle plate M16 inox 316',
    2, 677.45, 1354.90, 0.88,
    25, 'Inox 316', 0, FALSE, '2 semaines', 2
)
ON CONFLICT (id) DO NOTHING;

-- Mail reçu sans offre (visible en « brouillon » côté dashboard)
INSERT INTO email_requests (
    id, external_id, provider, from_address, subject, body_text, received_at, status
) VALUES (
    'a0000000-0000-4000-8000-000000000002',
    'seed-demo-002',
    'gmail',
    'marie.martin@indus-pro.fr',
    'Consultation prix — joints SPI',
    'Bonjour, pourriez-vous nous chiffrer 3 boîtes de joints SPI arbre transmission ? Merci, Marie Martin',
    NOW() - INTERVAL '30 minutes',
    'received'
) ON CONFLICT (id) DO NOTHING;
