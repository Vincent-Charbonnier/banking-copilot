"""ChromaDB retrieval helpers."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import chromadb
import httpx
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config.settings import settings
from app.models.schemas import RetrievedDocument

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load the configured sentence-transformers model once per process."""
    logger.info("Loading embedding model %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def _embedding_url() -> str:
    """Return the configured OpenAI-compatible embeddings URL."""
    return f"{settings.embedding_base_url.rstrip('/')}/embeddings"


def _remote_embeddings(texts: list[str]) -> list[list[float]]:
    """Call an OpenAI-compatible embeddings endpoint."""
    headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
    payload = {"model": settings.embedding_model, "input": texts}
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(_embedding_url(), headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()["data"]
    return [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using the configured endpoint, with local fallback."""
    if not texts:
        return []

    if settings.embedding_base_url:
        try:
            logger.info("Embedding %s texts via %s", len(texts), settings.embedding_base_url)
            return _remote_embeddings(texts)
        except Exception as exc:
            logger.warning("Remote embedding failed, falling back to local sentence-transformers: %s", exc)

    return get_embedding_model().encode(texts, normalize_embeddings=True).tolist()


class VectorStore:
    """Small wrapper around ChromaDB collections used by the demo."""

    def __init__(self) -> None:
        if settings.chroma_mode == "http":
            logger.info(
                "Connecting to ChromaDB HTTP server at %s:%s ssl=%s",
                settings.chroma_host,
                settings.chroma_port,
                settings.chroma_ssl,
            )
            self.client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                ssl=settings.chroma_ssl,
                tenant=settings.chroma_tenant,
                database=settings.chroma_database,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            return

        logger.info("Using persistent ChromaDB path %s", settings.chroma_path)
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def get_collection(self, name: str) -> Any:
        """Return a Chroma collection by name."""
        return self.client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def reset_collection(self, name: str) -> Any:
        """Delete and recreate a collection."""
        try:
            self.client.delete_collection(name=name)
        except Exception:
            logger.debug("Collection %s did not exist before reset", name)
        return self.get_collection(name)

    def has_index(self) -> bool:
        """Return true when both required collections contain documents."""
        try:
            products = self.client.get_collection("products")
            policies = self.client.get_collection("policies")
            return products.count() > 0 and policies.count() > 0
        except Exception:
            return False

    def search(self, collection_name: str, query: str, limit: int = 4) -> list[RetrievedDocument]:
        """Search a Chroma collection and return normalized chunks."""
        collection = self.get_collection(collection_name)
        query_embedding = embed_texts([query])[0]
        result: dict[str, Any] = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        retrieved: list[RetrievedDocument] = []
        for chunk, metadata, distance in zip(documents, metadatas, distances, strict=False):
            score = None if distance is None else round(1 - float(distance), 4)
            retrieved.append(
                RetrievedDocument(
                    document_type=str(metadata.get("document_type", collection_name[:-1])),
                    document_name=str(metadata.get("document_name", "Unknown")),
                    chunk=chunk,
                    score=score,
                )
            )
        return retrieved
