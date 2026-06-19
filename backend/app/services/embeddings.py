import asyncio

from openai import AsyncOpenAI

from app.config import settings


async def generate_embedding(text: str) -> list[float]:
    """Génère un vecteur d'embedding pour une requête ou un article catalogue."""
    normalized = text.strip().replace("\n", " ")
    if not normalized:
        raise ValueError("Le texte à vectoriser ne peut pas être vide")

    if settings.embedding_provider == "mistral":
        if not settings.mistral_api_key:
            raise ValueError("MISTRAL_API_KEY requis pour embedding_provider=mistral")

        def _mistral_embed() -> list[float]:
            from mistralai.client import Mistral

            client = Mistral(api_key=settings.mistral_api_key)
            response = client.embeddings.create(
                model=settings.embedding_model or "mistral-embed",
                inputs=[normalized],
            )
            return response.data[0].embedding

        return await asyncio.to_thread(_mistral_embed)
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY requis pour embedding_provider=openai")
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=normalized,
    )
    return response.data[0].embedding
