-- ============================================================================
-- BOSS — Initialisation PostgreSQL + pgvector
-- ============================================================================
-- Exécuter avec : psql $DATABASE_URL < database/init-pgvector.sql
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Schéma principal
\i database/schema.sql

-- Migrations
\i database/migrations/001_quote_dashboard_fields.sql
\i database/migrations/002_email_external_id_unique.sql

-- Données de test (optionnel)
-- INSERT INTO catalog_items (sku, name, description, category, unit_price, currency, stock_quantity)
-- VALUES 
--   ('SKU-001', 'Roulement à billes', 'Roulement 6205 2RS', 'Roulements', 15.50, 'EUR', 100),
--   ('SKU-002', 'Vis M8', 'Vis acier M8x30 DIN 912', 'Vis', 0.45, 'EUR', 5000);

\echo '✅ Schéma BOSS initialisé avec pgvector'

