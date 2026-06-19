"""Initialise PostgreSQL Boss (extensions, schéma, migrations).

Utilise asyncpg directement — aucune dépendance à psql ou aux outils système.

Usage :
  cd backend
  python -m scripts.init_database

Sur Railway (shell du service BOSS) :
  python -m scripts.init_database
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "database"

SQL_FILES = [
    DATABASE_DIR / "schema.sql",
    DATABASE_DIR / "migrations" / "001_quote_dashboard_fields.sql",
    DATABASE_DIR / "migrations" / "002_email_external_id_unique.sql",
]

# Codes d'erreur PostgreSQL que l'on tolère (objets déjà existants)
_IGNORABLE_PG_CODES = {
    "42P07",  # duplicate_table
    "42710",  # duplicate_object  (extension, type, index…)
    "42701",  # duplicate_column
    "42P06",  # duplicate_schema
}


async def _exec_sql_file(conn: asyncpg.Connection, sql_file: Path) -> None:
    """Exécute un fichier SQL entier dans une transaction unique."""
    sql = sql_file.read_text(encoding="utf-8")
    try:
        await conn.execute(sql)
    except asyncpg.PostgresError as exc:
        if exc.sqlstate in _IGNORABLE_PG_CODES:
            print(f"   ⚠ ignoré ({exc.sqlstate}) : {exc.args[0]}")
        else:
            raise


async def main_async() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL non définie.")

    for sql_file in SQL_FILES:
        if not sql_file.exists():
            raise SystemExit(f"Fichier introuvable : {sql_file}")

    conn: asyncpg.Connection = await asyncpg.connect(database_url)
    try:
        for sql_file in SQL_FILES:
            print(f"→ {sql_file.relative_to(PROJECT_ROOT)}")
            await _exec_sql_file(conn, sql_file)
    except asyncpg.PostgresError as exc:
        print(f"Erreur PostgreSQL ({exc.sqlstate}) : {exc.args[0]}", file=sys.stderr)
        raise SystemExit(f"Échec SQL : {exc.args[0]}") from exc
    finally:
        await conn.close()

    print("Base initialisée avec succès.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
