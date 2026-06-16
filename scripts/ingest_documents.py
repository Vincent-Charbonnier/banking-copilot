"""Ingest generated PDF documents into ChromaDB."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pypdf import PdfReader

from app.rag.vector_store import VectorStore, get_embedding_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def read_pdf(path: Path) -> str:
    """Extract text from a PDF."""
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 140) -> list[str]:
    """Chunk text with word boundaries and overlap."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        if end < len(cleaned):
            boundary = cleaned.rfind(" ", start, end)
            if boundary > start + 200:
                end = boundary
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def document_name_from_path(path: Path) -> str:
    """Convert generated PDF filename to display name."""
    return path.stem.replace("_", " ")


def ingest_directory(directory: Path, collection_name: str, document_type: str, store: VectorStore) -> int:
    """Ingest all PDFs in a directory into one Chroma collection."""
    collection = store.reset_collection(collection_name)
    model = get_embedding_model()
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, str | int]] = []

    for pdf_path in sorted(directory.glob("*.pdf")):
        chunks = chunk_text(read_pdf(pdf_path))
        for index, chunk in enumerate(chunks):
            document_name = document_name_from_path(pdf_path)
            ids.append(f"{document_type}-{pdf_path.stem}-{index}")
            documents.append(chunk)
            metadatas.append(
                {
                    "document_type": document_type,
                    "document_name": document_name,
                    "chunk_index": index,
                    "source_file": str(pdf_path),
                }
            )

    if not documents:
        logger.warning("No documents found in %s", directory)
        return 0

    embeddings = model.encode(documents, normalize_embeddings=True).tolist()
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    logger.info("Ingested %s chunks into %s", len(documents), collection_name)
    return len(documents)


def main() -> None:
    """Ingest product and policy documents."""
    store = VectorStore()
    product_chunks = ingest_directory(Path("data/products"), "products", "product", store)
    policy_chunks = ingest_directory(Path("data/policies"), "policies", "policy", store)
    print("Ingested:")
    print(f"- {product_chunks} product chunks")
    print(f"- {policy_chunks} policy chunks")


if __name__ == "__main__":
    main()
