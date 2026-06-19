from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CatalogMatch(BaseModel):
    id: UUID
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    unit_price: float
    currency: str = "EUR"
    similarity: float = Field(ge=0, le=1, description="Score cosine (1 = identique)")
    conditionnement: int | None = None
    en_stock: bool | None = None
    delai_livraison: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=1, ge=1, le=20)


class SemanticSearchResponse(BaseModel):
    query: str
    matches: list[CatalogMatch]
