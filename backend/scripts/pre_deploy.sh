#!/usr/bin/env bash
# =============================================================================
# pre_deploy.sh — Initialisation de la base de données avant déploiement BOSS
# =============================================================================
# Exécute init_db_async.py pour créer les tables, extensions et indexes
# pgvector si la base est vide ou partiellement initialisée.
#
# Usage Railway (pre-deploy hook) :
#   bash backend/scripts/pre_deploy.sh
#
# Usage manuel depuis le shell Railway :
#   cd /app/backend && bash scripts/pre_deploy.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[pre_deploy] Répertoire backend : ${BACKEND_DIR}"
cd "${BACKEND_DIR}"

# Vérification que DATABASE_URL est défini
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "[pre_deploy] ERREUR : DATABASE_URL n'est pas défini." >&2
    exit 1
fi

echo "[pre_deploy] Initialisation de la base de données PostgreSQL + pgvector…"
python -m scripts.init_db_async

echo "[pre_deploy] ✓ Initialisation terminée."
