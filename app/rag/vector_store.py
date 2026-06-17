"""ChromaDB retrieval helpers."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
import httpx
from chromadb.config import Settings as ChromaSettings

from app.config.settings import settings
from app.models.schemas import RetrievedDocument

logger = logging.getLogger(__name__)


def normalize_embedding_url(endpoint: str) -> str:
    """Normalize an embedding endpoint to an OpenAI-compatible embeddings URL."""
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/embeddings"):
        return endpoint
    if endpoint.endswith("/v1"):
        return f"{endpoint}/embeddings"
    return f"{endpoint}/v1/embeddings"


def _remote_embeddings(texts: list[str], input_type: str) -> list[list[float]]:
    """Call an OpenAI-compatible embeddings endpoint."""
    headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
    payload = {"model": settings.embedding_model, "input": texts, "input_type": input_type}
    with httpx.Client(timeout=settings.llm_timeout_seconds, verify=settings.embedding_ssl_verify) as client:
        embedding_url = normalize_embedding_url(settings.embedding_base_url)
        response = client.post(embedding_url, headers=headers, json=payload)
        if response.status_code in {400, 422}:
            payload.pop("input_type", None)
            response = client.post(embedding_url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} from {embedding_url}: {response.text[:1000]}")
        data = response.json()["data"]
    return [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]


def embed_texts(texts: list[str], input_type: str = "passage") -> list[list[float]]:
    """Embed texts using the configured remote OpenAI-compatible endpoint."""
    if not texts:
        return []

    if not settings.embedding_base_url:
        raise RuntimeError("Embedding endpoint is not configured. Set it in Settings before indexing or searching.")

    try:
        logger.info("Embedding %s texts via %s", len(texts), settings.embedding_base_url)
        return _remote_embeddings(texts, input_type)
    except Exception as exc:
        raise RuntimeError(f"Remote embedding failed: {exc}") from exc


class VectorStore:
    """Small wrapper around ChromaDB collections used by the demo."""

    def __init__(self) -> None:
        if settings.chroma_mode != "http":
            raise RuntimeError("Only remote ChromaDB HTTP mode is supported.")
        if not settings.chroma_host:
            raise RuntimeError("ChromaDB endpoint is not configured. Set it in Settings before indexing or searching.")

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
            settings=ChromaSettings(
                anonymized_telemetry=False,
                chroma_server_ssl_verify=settings.chroma_ssl_verify,
            ),
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
        query_embedding = embed_texts([query], input_type="query")[0]
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
