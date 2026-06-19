from fastapi import APIRouter, HTTPException

from app.models.catalog import SemanticSearchRequest, SemanticSearchResponse
from app.services.vector_search import search_catalog_by_semantic_query

router = APIRouter(prefix="/search", tags=["Recherche catalogue"])


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(body: SemanticSearchRequest) -> SemanticSearchResponse:
    """
    Endpoint FastAPI : prend une chaîne (pièce demandée), génère son embedding,
    effectue la similarité cosinus dans PostgreSQL et retourne les meilleurs matchs.
    """
    try:
        matches = await search_catalog_by_semantic_query(
            body.query,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erreur recherche vectorielle") from exc

    return SemanticSearchResponse(query=body.query, matches=matches)
