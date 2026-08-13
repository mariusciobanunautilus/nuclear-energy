from __future__ import annotations

from collections.abc import Sequence

from openai import OpenAI

from nuclear_energy.config import get_settings


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
DEFAULT_EMBEDDING_BATCH_SIZE = 32


def get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to create embeddings.")
    return OpenAI(api_key=settings.openai_api_key)


def create_embedding(
    text: str,
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
    dimensions: int | None = EMBEDDING_DIMENSIONS,
    client: object | None = None,
) -> list[float]:
    return create_embeddings([text], model=model, dimensions=dimensions, client=client)[0]


def create_embeddings(
    texts: Sequence[str],
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
    dimensions: int | None = EMBEDDING_DIMENSIONS,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    client: object | None = None,
) -> list[list[float]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    prepared_texts = [_prepare_embedding_input(text) for text in texts]
    if not prepared_texts:
        return []

    active_client = client or get_openai_client()
    embeddings: list[list[float]] = []

    for start in range(0, len(prepared_texts), batch_size):
        batch = prepared_texts[start : start + batch_size]
        request = {
            "input": batch,
            "model": model,
            "encoding_format": "float",
        }
        if dimensions is not None:
            request["dimensions"] = dimensions

        response = active_client.embeddings.create(**request)  # type: ignore[attr-defined]
        ordered_data = sorted(response.data, key=lambda item: item.index)
        if len(ordered_data) != len(batch):
            raise RuntimeError("OpenAI returned a different number of embeddings than requested.")

        embeddings.extend([list(item.embedding) for item in ordered_data])

    return embeddings


def dimensions_for_model(model: str) -> int | None:
    if model.startswith("text-embedding-3"):
        return EMBEDDING_DIMENSIONS
    return None


def _prepare_embedding_input(text: str) -> str:
    prepared = " ".join(text.split())
    if not prepared:
        raise ValueError("Embedding input cannot be empty.")
    return prepared
