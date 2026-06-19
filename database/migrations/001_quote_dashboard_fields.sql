-- Migration : champs dashboard BOSS (alignés articles_industriels_1000.xlsx)

ALTER TABLE quotes
    ADD COLUMN IF NOT EXISTS numero_offre VARCHAR(32),
    ADD COLUMN IF NOT EXISTS texte_intro TEXT,
    ADD COLUMN IF NOT EXISTS texte_conclusion TEXT;

ALTER TABLE quote_line_items
    ADD COLUMN IF NOT EXISTS conditionnement INTEGER,
    ADD COLUMN IF NOT EXISTS alliage VARCHAR(128),
    ADD COLUMN IF NOT EXISTS remise_pct REAL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS en_stock BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS delai_livraison VARCHAR(64),
    ADD COLUMN IF NOT EXISTS line_metadata JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_quotes_numero_offre ON quotes (numero_offre);
