"""ChromaDB retrieval helpers."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

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


class ChromaCollection:
    """Minimal ChromaDB HTTP collection wrapper that avoids client schema parsing."""

    def __init__(self, store: "VectorStore", name: str, collection_id: str) -> None:
        self.store = store
        self.name = name
        self.collection_id = collection_id

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        """Add embedded documents to the collection."""
        self.store.request(
            "post",
            f"/collections/{quote(self.collection_id, safe='')}/add",
            json={
                "ids": ids,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "documents": documents,
                "uris": None,
            },
        )

    def count(self) -> int:
        """Return collection document count."""
        result = self.store.request("get", f"/collections/{quote(self.collection_id, safe='')}/count")
        return int(result)

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, Any]:
        """Query nearest neighbors."""
        return self.store.request(
            "post",
            f"/collections/{quote(self.collection_id, safe='')}/query",
            json={
                "query_embeddings": query_embeddings,
                "n_results": n_results,
                "where": None,
                "where_document": None,
                "include": include,
            },
        )


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
        scheme = "https" if settings.chroma_ssl else "http"
        self.base_url = f"{scheme}://{settings.chroma_host}:{settings.chroma_port}/api/v2"
        self.tenant = settings.chroma_tenant
        self.database = settings.chroma_database
        self.http = httpx.Client(timeout=settings.llm_timeout_seconds, verify=settings.chroma_ssl_verify)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Call ChromaDB HTTP API and return decoded JSON."""
        url = (
            f"{self.base_url}/tenants/{quote(self.tenant, safe='')}"
            f"/databases/{quote(self.database, safe='')}{path}"
        )
        response = self.http.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"ChromaDB HTTP {response.status_code} from {url}: {response.text[:1000]}")
        if not response.text:
            return None
        return response.json()

    def heartbeat(self) -> Any:
        """Return ChromaDB identity to validate connectivity."""
        response = self.http.get(f"{self.base_url}/auth/identity")
        if response.status_code >= 400:
            raise RuntimeError(f"ChromaDB heartbeat failed: HTTP {response.status_code}: {response.text[:1000]}")
        return response.json()

    def get_collection(self, name: str) -> ChromaCollection:
        """Return a Chroma collection by name."""
        response = self.request(
            "post",
            "/collections",
            json={
                "name": name,
                "metadata": {"hnsw:space": "cosine"},
                "configuration": None,
                "get_or_create": True,
            },
        )
        return ChromaCollection(self, name, str(response["id"]))

    def reset_collection(self, name: str) -> ChromaCollection:
        """Delete and recreate a collection."""
        url_name = quote(name, safe="")
        try:
            self.request("delete", f"/collections/{url_name}")
        except Exception as exc:
            logger.debug("Collection %s did not exist before reset or could not be deleted: %s", name, exc)
        return self.get_collection(name)

    def has_index(self) -> bool:
        """Return true when both required collections contain documents."""
        try:
            products = self.get_collection("products")
            policies = self.get_collection("policies")
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
