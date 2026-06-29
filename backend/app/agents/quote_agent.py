"""
Agent PydanticAI Boss — extraction mail, recherche catalogue, offre structurée.
Observabilité : Langfuse via OpenTelemetry (Agent.instrument_all + instrument=True).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langfuse import get_client, observe, propagate_attributes
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.mistral import MistralModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.mistral import MistralProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.models.quote import ExtractedPart, QuoteLineItem, QuoteOffer
from app.services.quote_mappers import line_item_from_catalog_match
from app.services.vector_search import get_best_catalog_match

if settings.mistral_api_key:
    os.environ["MISTRAL_API_KEY"] = settings.mistral_api_key


def _build_llm_model() -> str | OpenAIChatModel | MistralModel:
    """Passe la clé API explicitement (évite les conflits avec une variable d'env stale)."""
    model_spec = settings.llm_model

    if model_spec.startswith("mistral:"):
        model_name = model_spec.split(":", 1)[1]
        if settings.mistral_api_key:
            return MistralModel(
                model_name,
                provider=MistralProvider(api_key=settings.mistral_api_key),
            )
        return model_spec

    if model_spec.startswith(("openai:", "openai-chat:")):
        model_name = model_spec.split(":", 1)[1]
        if settings.openai_api_key:
            return OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(api_key=settings.openai_api_key),
            )
        return f"openai-chat:{model_name}"

    return model_spec


_LLM_MODEL = _build_llm_model()

# ---------------------------------------------------------------------------
# Langfuse + instrumentation PydanticAI (à appeler une fois au démarrage)
# ---------------------------------------------------------------------------


def setup_langfuse_observability() -> None:
    """Configure OTel → Langfuse pour tracer LLM, outils et latence."""
    if settings.langfuse_public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    if settings.langfuse_secret_key:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)

    langfuse = get_client()
    try:
        if langfuse.auth_check():
            Agent.instrument_all()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dépendances injectées dans l'agent (connexion DB, contexte mail, etc.)
# ---------------------------------------------------------------------------


@dataclass
class QuoteAgentDeps:
    email_request_id: str
    customer_email: str


# ---------------------------------------------------------------------------
# Agent principal
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Tu es l'assistant commercial de Boss, spécialiste en pièces de rechange.
À partir du mail client fourni :
1. Identifie chaque pièce demandée et sa quantité.
2. Pour chaque pièce, appelle l'outil search_catalog pour trouver l'article catalogue et son prix.
3. Construis une offre commerciale professionnelle en français (formule, lignes, totaux TVA 20%, conditions).
Ne invente jamais de références catalogue : utilise uniquement les résultats de search_catalog.
Si aucun match catalogue, indique-le dans closing_notes et exclue la ligne du total."""

quote_agent = Agent(
    _LLM_MODEL,
    deps_type=QuoteAgentDeps,
    output_type=QuoteOffer,
    system_prompt=SYSTEM_PROMPT,
)


@quote_agent.tool
async def search_catalog(ctx: RunContext[QuoteAgentDeps], part_description: str) -> str:
    """
    Recherche sémantique dans le catalogue de 40k pièces Boss.
    Retourne SKU, nom, prix unitaire et score de similarité.
    """
    match = await get_best_catalog_match(part_description)
    if not match:
        return (
            f"Aucun article trouvé pour « {part_description} » "
            f"(seuil similarité {settings.vector_similarity_threshold})."
        )
    return (
        f"SKU={match.sku} | {match.name} | alliage={match.category} | "
        f"conditionnement={match.conditionnement} | prix_boite={match.unit_price} {match.currency} | "
        f"stock={'oui' if match.en_stock else 'non'} | delai={match.delai_livraison} | "
        f"similarité={match.similarity:.3f}"
    )


# ---------------------------------------------------------------------------
# Extraction structurée des entités (étape optionnelle / pipeline)
# ---------------------------------------------------------------------------

extraction_agent = Agent(
    _LLM_MODEL,
    output_type=list[ExtractedPart],
    system_prompt=(
        "Extrais toutes les pièces de rechange demandées avec leurs quantités "
        "depuis le mail client. Réponds uniquement avec la structure demandée."
    ),
)


@observe(name="boss-process-email-quote")
async def process_email_into_quote(
    email_body: str,
    *,
    deps: QuoteAgentDeps,
    session_id: str | None = None,
) -> QuoteOffer:
    """
    Pipeline complet : mail → agent → offre structurée, tracé dans Langfuse.
    """
    langfuse = get_client()

    with propagate_attributes(
        session_id=session_id or deps.email_request_id,
        user_id=deps.customer_email,
        tags=["boss", "quote-agent"],
        metadata={"email_request_id": deps.email_request_id},
    ):
        result = await quote_agent.run(
            f"Mail client à traiter :\n\n{email_body}",
            deps=deps,
        )
        offer: QuoteOffer = result.output

    langfuse.flush()
    return offer


async def extract_parts_from_email(email_body: str) -> list[ExtractedPart]:
    """Extraction Pydantic des entités avant recherche vectorielle batch."""
    result = await extraction_agent.run(email_body)
    return result.output


async def build_quote_lines_from_parts(parts: list[ExtractedPart]) -> list[QuoteLineItem]:
    """Mappe chaque pièce extraite vers le catalogue via pgvector."""
    lines: list[QuoteLineItem] = []
    for part in parts:
        match = await get_best_catalog_match(part.description)
        if not match:
            continue
        lines.append(line_item_from_catalog_match(part.description, part.quantity, match))
    return lines
