"""Initialise PostgreSQL Boss (extensions, schéma, migrations).

Usage :
  cd backend
  python -m scripts.init_database

Sur Railway (shell du service BOSS) :
  python -m scripts.init_database
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "database"

SQL_FILES = [
    DATABASE_DIR / "schema.sql",
    DATABASE_DIR / "migrations" / "001_quote_dashboard_fields.sql",
    DATABASE_DIR / "migrations" / "002_email_external_id_unique.sql",
]


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL non définie.")

    for sql_file in SQL_FILES:
        if not sql_file.exists():
            raise SystemExit(f"Fichier introuvable : {sql_file}")

        print(f"→ {sql_file.relative_to(PROJECT_ROOT)}")
        result = subprocess.run(
            ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", str(sql_file)],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.returncode != 0:
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
            raise SystemExit(f"Échec SQL : {sql_file.name}")

    print("Base initialisée avec succès.")


if __name__ == "__main__":
    main()
