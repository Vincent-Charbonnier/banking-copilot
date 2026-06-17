#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}:."

eval "$(python scripts/export_runtime_settings.py)"

export HF_HOME="${HF_HOME:-/app/data/cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-/app/data/cache/huggingface/transformers}"
export SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/app/data/cache/sentence-transformers}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/app/data/cache}"
mkdir -p "${HF_HOME}" "${TRANSFORMERS_CACHE}" "${SENTENCE_TRANSFORMERS_HOME}" "${XDG_CACHE_HOME}"

if [ ! -f "data/customers/customer_001.json" ] || [ ! -f "data/products/Auto_Loan_Plus.pdf" ] || [ ! -f "data/policies/Lending_Policy.pdf" ]; then
  echo "Demo data missing. Generating fictional data..."
  python scripts/generate_demo_data.py
fi

if [ "${CHROMA_MODE:-http}" = "http" ] && [ -z "${CHROMA_HOST:-}" ]; then
  echo "ChromaDB is not configured. Skipping ChromaDB wait and document ingestion until Settings are saved and Reindex is run."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8080
fi

if [ "${CHROMA_MODE:-http}" = "http" ]; then
  echo "Waiting for ChromaDB HTTP server at ${CHROMA_HOST:-localhost}:${CHROMA_PORT:-8000}..."
  python - <<'PY'
import time

from app.rag.vector_store import VectorStore

last_error = None
for _ in range(60):
    try:
        VectorStore().heartbeat()
        raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(1)
raise SystemExit(f"ChromaDB server was not ready: {last_error}")
PY
fi

if python - <<'PY'
from app.rag.vector_store import VectorStore

raise SystemExit(0 if VectorStore().has_index() else 1)
PY
then
  echo "Chroma collections found."
else
  echo "Chroma collections missing. Ingesting generated documents..."
  python scripts/ingest_documents.py
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8080
