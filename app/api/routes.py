"""FastAPI routes for the Retail Banking Advisor Copilot."""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException

from app.agent.banking_agent import BankingAgent
from app.config.settings import settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Customer,
    HealthResponse,
    Interaction,
    RuntimeSettings,
    RuntimeSettingsUpdate,
)
from app.services.customer_service import CustomerService
from app.services.settings_service import get_runtime_settings, update_runtime_settings

logger = logging.getLogger(__name__)

router = APIRouter()
customer_service = CustomerService()
agent = BankingAgent()


def rebuild_agent() -> None:
    """Recreate the agent after runtime model or Chroma settings change."""
    global agent
    agent = BankingAgent()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", app=settings.app_name)


@router.get("/customers", response_model=list[Customer], tags=["customers"])
def list_customers() -> list[Customer]:
    """List all fictional customers."""
    return customer_service.list_customers()


@router.get("/customer/{customer_id}", response_model=Customer, tags=["customers"])
def get_customer(customer_id: str) -> Customer:
    """Get one fictional customer profile."""
    try:
        return customer_service.get_customer(customer_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/customer/{customer_id}/interactions", response_model=list[Interaction], tags=["customers"])
def get_customer_interactions(customer_id: str) -> list[Interaction]:
    """Get recent customer interactions."""
    return customer_service.get_interactions(customer_id)


@router.post("/chat", response_model=ChatResponse, tags=["agent"])
def chat(request: ChatRequest) -> ChatResponse:
    """Run the advisor copilot for a chat message."""
    try:
        return agent.run(request.message, request.customer_id, request.history)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/settings", response_model=RuntimeSettings, tags=["settings"])
def read_settings() -> RuntimeSettings:
    """Return current runtime settings without exposing the LLM API key."""
    return get_runtime_settings()


@router.put("/settings", response_model=RuntimeSettings, tags=["settings"])
def update_settings(update: RuntimeSettingsUpdate) -> RuntimeSettings:
    """Update runtime settings for the current backend process."""
    try:
        updated = update_runtime_settings(update)
        rebuild_agent()
        return updated
    except Exception as exc:
        logger.exception("Settings update failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reindex", tags=["rag"])
def reindex() -> dict[str, str]:
    """Rebuild ChromaDB indexes from generated PDF documents."""
    env = os.environ.copy()
    env.update(
        {
            "CHROMA_PATH": str(settings.chroma_path),
            "CHROMA_MODE": settings.chroma_mode,
            "CHROMA_HOST": settings.chroma_host,
            "CHROMA_PORT": str(settings.chroma_port),
            "CHROMA_SSL": str(settings.chroma_ssl).lower(),
            "CHROMA_TENANT": settings.chroma_tenant,
            "CHROMA_DATABASE": settings.chroma_database,
            "EMBEDDING_MODEL": settings.embedding_model,
            "ANONYMIZED_TELEMETRY": "False",
        }
    )
    try:
        subprocess.run([sys.executable, "scripts/ingest_documents.py"], check=True, env=env)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}") from exc
    rebuild_agent()
    return {"status": "reindexed"}
