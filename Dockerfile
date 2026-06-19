FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY database/ database/
COPY articles_industriels_1000.xlsx .
COPY offre_de_prix_BOSS.docx .

WORKDIR /app/backend

ENV CATALOG_XLSX_PATH=/app/articles_industriels_1000.xlsx
ENV DOCX_TEMPLATE_PATH=/app/offre_de_prix_BOSS.docx

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
