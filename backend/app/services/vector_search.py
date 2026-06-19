import json
from typing import Any
from uuid import UUID

import asyncpg

from app.config import settings
from app.db import get_pool
from app.models.catalog import CatalogMatch
from app.services.embeddings import generate_embedding


def _embedding_to_pgvector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(v) for v in vector) + "]"


def _parse_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _row_to_catalog_match(row: asyncpg.Record, *, similarity: float = 1.0) -> CatalogMatch:
    metadata = _parse_metadata(row.get("metadata"))
    en_stock_raw = metadata.get("en_stock")
    return CatalogMatch(
        id=row["id"],
        sku=row["sku"],
        name=row["name"],
        description=row.get("description"),
        category=row.get("category"),
        unit_price=row["unit_price"],
        currency=row.get("currency") or "EUR",
        similarity=similarity,
        conditionnement=metadata.get("conditionnement"),
        en_stock=en_stock_raw if isinstance(en_stock_raw, bool) else None,
        delai_livraison=metadata.get("delai_livraison"),
        metadata=metadata,
    )


async def search_catalog_by_semantic_query(
    query: str,
    *,
    limit: int | None = None,
    min_similarity: float | None = None,
) -> list[CatalogMatch]:
    limit = limit or settings.vector_search_limit
    min_similarity = (
        min_similarity if min_similarity is not None else settings.vector_similarity_threshold
    )

    embedding = await generate_embedding(query)
    vector_literal = _embedding_to_pgvector_literal(embedding)

    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            id,
            sku,
            name,
            description,
            category,
            unit_price::float8 AS unit_price,
            currency,
            metadata,
            1 - (embedding <=> $1::vector) AS similarity
        FROM catalog_items
        WHERE embedding IS NOT NULL
          AND 1 - (embedding <=> $1::vector) >= $2
        ORDER BY embedding <=> $1::vector
        LIMIT $3
        """,
        vector_literal,
        min_similarity,
        limit,
    )

    return [_row_to_catalog_match(row, similarity=row["similarity"]) for row in rows]


async def get_best_catalog_match(query: str) -> CatalogMatch | None:
    matches = await search_catalog_by_semantic_query(query, limit=1)
    return matches[0] if matches else None


async def get_catalog_item_by_id(item_id: UUID) -> CatalogMatch | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, sku, name, description, category,
               unit_price::float8 AS unit_price, currency, metadata
        FROM catalog_items WHERE id = $1
        """,
        item_id,
    )
    if not row:
        return None
    return _row_to_catalog_match(row)
