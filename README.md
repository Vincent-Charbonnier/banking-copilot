# Banking Copilot

A minimal retail banking AI copilot with RAG (Retrieval Augmented Generation).

## Features

- Banking dashboard with account overview and transactions
- AI-powered banking assistant using external LLM and embedding services
- RAG implementation with ChromaDB vector database
- Single Docker container deployment

## Prerequisites

- Docker
- External OpenAI-compatible LLM API
- External OpenAI-compatible embedding API
- External ChromaDB HTTP server

## Quick Start

1. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
# Edit .env with your API keys and ChromaDB settings
```

2. Run with Docker:
```bash
docker run -p 8501:8501 -p 8000:8000 --env-file .env vinchar/new-retail-banking:latest
```

3. Open browser: http://localhost:8501

## Configuration

All configuration via environment variables:

- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` - LLM service
- `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL` - Embedding service  
- `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_SSL`, `CHROMA_COLLECTION` - ChromaDB
- `BACKEND_URL` - FastAPI backend URL (default: http://localhost:8000)

## Kubernetes Deployment

```bash
helm install banking-copilot ./deploy/helm/new-banking-copilot
```

## Architecture

- **Frontend**: Streamlit (port 8501)
- **Backend**: FastAPI (port 8000)
- **AI**: External LLM and embedding APIs
- **Vector DB**: External ChromaDB HTTP server
