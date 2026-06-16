#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}:."

if [ ! -f "data/customers/customer_001.json" ] || [ ! -f "data/products/Auto_Loan_Plus.pdf" ] || [ ! -f "data/policies/Lending_Policy.pdf" ]; then
  echo "Demo data missing. Generating fictional data..."
  python scripts/generate_demo_data.py
fi

if [ "${CHROMA_MODE:-persistent}" = "http" ]; then
  echo "Waiting for ChromaDB HTTP server at ${CHROMA_HOST:-localhost}:${CHROMA_PORT:-8000}..."
  python - <<'PY'
import time

from app.rag.vector_store import VectorStore

last_error = None
for _ in range(60):
    try:
        VectorStore().client.heartbeat()
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

uvicorn app.main:app --host 0.0.0.0 --port 8080 &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

streamlit run frontend/streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --browser.gatherUsageStats false
