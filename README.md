# Boss — Automatisation des demandes de prix

Application full stack pour traiter les consultations clients par mail, mapper les pièces au catalogue (RAG pgvector) et valider les offres via un dashboard Next.js.

## Structure

```
BOSS/
├── database/schema.sql      # PostgreSQL + pgvector (HNSW)
├── backend/                 # FastAPI, PydanticAI, Langfuse
└── frontend/                # Next.js App Router + Tailwind
```

## Démarrage rapide

### 1. Base de données

```bash
psql $DATABASE_URL -f database/schema.sql
```

Adapter `vector(1024)` → `vector(1536)` si vous utilisez OpenAI `text-embedding-3-small`.

### 2. Backend (Railway)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env     # renseigner les clés
uvicorn app.main:app --reload --port 8000
```

**Recherche sémantique :**

```bash
curl -X POST http://localhost:8000/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "joint spi arbre transmission", "limit": 3}'
```

### 3. Frontend (Vercel)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Dashboard : `http://localhost:3000/dashboard`

Le dashboard employé (1440×665) utilise des **données de démo** alignées sur le catalogue Excel
(`959310YH`, `511615MW`, `908386HR`…) tant que le backend n'est pas connecté (`NEXT_PUBLIC_USE_DEMO=true`).

### 4. Ingestion catalogue

Fichier métier : `articles_industriels_1000.xlsx` (1000 articles BOSS).

```bash
cd backend
pip install -r requirements.txt

# Valider la lecture du Excel (sans base ni API)
python -m scripts.ingest_catalog --xlsx ../articles_industriels_1000.xlsx --parse-only

# Ingestion complète → embeddings + PostgreSQL
python -m scripts.ingest_catalog --xlsx ../articles_industriels_1000.xlsx

# Test sur 10 articles seulement
python -m scripts.ingest_catalog --xlsx ../articles_industriels_1000.xlsx --limit 10
```

Mapping Excel → `catalog_items` :

| Colonne Excel | Champ DB |
|---|---|
| Référence | `sku` |
| Désignation | `name` |
| Alliage | `category` |
| Prix boîte (€) | `unit_price` |
| Qtité conditionnement / En stock / Délai | `metadata` JSONB |

## Génération DOCX (offre_de_prix_BOSS.docx)

À la validation, le backend remplit le modèle Word BOSS et enregistre le fichier dans `backend/output/offres/`.

```bash
# Test sans base de données
cd backend
python -m scripts.test_docx_generation
```

**Endpoints API :**
- `POST /api/v1/quotes/generate-document` — génère un DOCX depuis le payload offre (mode démo)
- `GET /api/v1/quotes/{id}/document` — télécharge le DOCX d'une offre persistée

**Dashboard :** bouton « Télécharger DOCX » ou téléchargement automatique à la validation.

## Boîte mail test (réception IMAP)

`contact@boss-industrie.fr` dans le modèle Word est **fictif**. Pour tester la réception, utilisez une **vraie boîte Gmail de test** :

1. Créer un compte Gmail dédié (ex. `boss.devis.test@gmail.com`)
2. Activer la **validation en 2 étapes**
3. Générer un **mot de passe d'application** : [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Copier les variables dans `backend/.env` (voir `.env.example`)

```bash
# Tester la connexion IMAP
cd backend
python -m scripts.sync_inbox --test

# Synchroniser les mails non lus → table email_requests
python -m scripts.sync_inbox
```

**Endpoints API :**
- `GET /api/v1/emails/config` — état de la configuration mail
- `GET /api/v1/emails/test-connection` — test IMAP
- `POST /api/v1/emails/sync` — synchroniser la boîte
- `GET /api/v1/emails` — liste des demandes reçues
- `POST /api/v1/emails/{id}/process` — lancer l'agent IA → créer une offre

Migration recommandée (évite les doublons à la sync) :

```bash
psql $DATABASE_URL -f database/migrations/002_email_external_id_unique.sql
```

## Observabilité Langfuse

- `Agent.instrument_all()` au démarrage FastAPI
- `instrument=True` sur chaque agent PydanticAI
- `@observe` sur `process_email_into_quote` avec `session_id` = ID demande mail

Traces visibles sur [cloud.langfuse.com](https://cloud.langfuse.com).

## CI/CD (à brancher)

- **GitHub Actions** : lint + tests backend, build Next.js
- **Railway** : déploiement `uvicorn app.main:app`
- **Vercel** : déploiement frontend avec `NEXT_PUBLIC_API_URL`
