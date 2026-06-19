#!/usr/bin/env python3
"""
Initialise la base de données PostgreSQL + pgvector pour BOSS.
Exécution : python -m scripts.init_db
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

async def init_database():
    """Initialise le schéma PostgreSQL + pgvector."""
    
    # Récupérer la DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Erreur : DATABASE_URL non définie")
        return 1
    
    print(f"📦 Connexion à PostgreSQL...")
    
    try:
        # Connexion
        conn = await asyncpg.connect(database_url)
        
        # 1. Extensions
        print("📦 Création des extensions...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        
        # 2. Schéma principal
        print("📦 Création du schéma...")
        schema_path = Path(__file__).parent.parent.parent / "database" / "schema.sql"
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        
        # Exécuter le schéma ligne par ligne (ignorer les CREATE EXTENSION)
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                try:
                    await conn.execute(statement)
                except asyncpg.exceptions.DuplicateObjectError:
                    pass  # Ignorer les objets déjà existants
        
        # 3. Migrations
        print("📦 Exécution des migrations...")
        migrations_dir = Path(__file__).parent.parent.parent / "database" / "migrations"
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            print(f"  → {migration_file.name}")
            with open(migration_file, "r") as f:
                migration_sql = f.read()
            
            for statement in migration_sql.split(";"):
                statement = statement.strip()
                if statement and not statement.startswith("--"):
                    try:
                        await conn.execute(statement)
                    except asyncpg.exceptions.DuplicateObjectError:
                        pass
        
        await conn.close()
        
        print("✅ Base de données initialisée avec succès !")
        return 0
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(init_database())
    sys.exit(exit_code)

