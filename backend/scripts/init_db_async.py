#!/usr/bin/env python3
"""
Initialise la base de données PostgreSQL + pgvector pour BOSS.
Exécution : python -m scripts.init_db_async
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
        
        # Lire et exécuter le SQL d'initialisation
        init_sql_path = Path(__file__).parent.parent.parent / "database" / "init-all.sql"
        with open(init_sql_path, "r") as f:
            init_sql = f.read()
        
        print("📦 Exécution du schéma complet...")
        await conn.execute(init_sql)
        
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

