#!/bin/bash
# Script pré-déploiement : initialise la base de données

set -e

echo "🚀 Pré-déploiement BOSS"
echo "========================"

# Vérifier que DATABASE_URL est définie
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL non définie, initialisation DB ignorée"
    exit 0
fi

echo "📦 Initialisation de la base de données..."
cd /app/backend
python scripts/init_db.py

echo "✅ Pré-déploiement terminé"

