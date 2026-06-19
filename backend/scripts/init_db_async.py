"""
Initialisation complète de la base de données PostgreSQL + pgvector pour BOSS.

Lit DATABASE_URL depuis les variables d'environnement (ou backend/.env),
se connecte via asyncpg et exécute database/init-all.sql.

Usage :
  cd backend
  python -m scripts.init_db_async

Variables d'environnement requises :
  DATABASE_URL  — URL PostgreSQL (ex: postgresql://user:pass@host:5432/db)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

# Résolution du chemin vers init-all.sql depuis la racine du projet
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_SQL_FILE = _PROJECT_ROOT / "database" / "init-all.sql"


def _get_database_url() -> str:
    """Récupère DATABASE_URL via pydantic-settings (lit aussi backend/.env)."""
    try:
        from app.config import settings  # noqa: PLC0415

        return settings.database_url
    except Exception as exc:  # noqa: BLE001
        print(f"[init_db] Impossible de charger app.config.settings : {exc}", file=sys.stderr)
        print("[init_db] Tentative de lecture directe de DATABASE_URL…", file=sys.stderr)

    import os

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL est absent des variables d'environnement et de backend/.env"
        )
    return url


async def init_db() -> None:
    """Exécute init-all.sql sur la base cible."""
    if not _SQL_FILE.exists():
        raise SystemExit(f"Fichier SQL introuvable : {_SQL_FILE}")

    sql = _SQL_FILE.read_text(encoding="utf-8")
    database_url = _get_database_url()

    # asyncpg n'accepte pas le préfixe "postgresql+asyncpg://"
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"[init_db] Connexion à la base de données…")
    conn: asyncpg.Connection = await asyncpg.connect(conn_url)

    try:
        print(f"[init_db] Exécution de {_SQL_FILE.name} ({len(sql)} caractères)…")
        await conn.execute(sql)
        print("[init_db] ✓ Base de données initialisée avec succès.")
        print("[init_db]   Tables créées : catalog_items, email_requests, quotes, quote_line_items")
        print("[init_db]   Extensions    : vector, uuid-ossp")
        print("[init_db]   Index HNSW    : idx_catalog_items_embedding_hnsw")
    except asyncpg.PostgresError as exc:
        print(f"[init_db] ✗ Erreur PostgreSQL : {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
