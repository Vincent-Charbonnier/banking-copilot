"""Runtime settings updates for the local demo process."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.config.settings import settings
from app.models.schemas import RuntimeSettings, RuntimeSettingsUpdate
from app.rag.vector_store import get_embedding_model

logger = logging.getLogger(__name__)


def get_runtime_settings() -> RuntimeSettings:
    """Return the current process settings without exposing the API key."""
    return RuntimeSettings.model_validate(settings.as_public_dict())


def persist_runtime_settings() -> None:
    """Write current runtime settings to durable local storage."""
    settings.runtime_settings_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = settings.runtime_settings_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(settings.as_persisted_dict(), indent=2), encoding="utf-8")
    temp_path.replace(settings.runtime_settings_path)
    logger.info("Persisted runtime settings to %s", settings.runtime_settings_path)


def update_runtime_settings(update: RuntimeSettingsUpdate) -> RuntimeSettings:
    """Apply and persist runtime settings for the current FastAPI process."""
    settings.llm_base_url = update.llm_base_url.rstrip("/")
    settings.llm_model = update.llm_model
    if update.llm_api_key:
        settings.llm_api_key = update.llm_api_key
    settings.embedding_model = update.embedding_model
    settings.chroma_mode = update.chroma_mode
    settings.chroma_path = Path(update.chroma_path)
    settings.chroma_host = update.chroma_host
    settings.chroma_port = update.chroma_port
    settings.chroma_ssl = update.chroma_ssl
    settings.chroma_tenant = update.chroma_tenant
    settings.chroma_database = update.chroma_database
    settings.llm_timeout_seconds = update.llm_timeout_seconds

    os.environ["LLM_BASE_URL"] = settings.llm_base_url
    os.environ["LLM_MODEL"] = settings.llm_model
    os.environ["LLM_API_KEY"] = settings.llm_api_key
    os.environ["EMBEDDING_MODEL"] = settings.embedding_model
    os.environ["CHROMA_MODE"] = settings.chroma_mode
    os.environ["CHROMA_PATH"] = str(settings.chroma_path)
    os.environ["CHROMA_HOST"] = settings.chroma_host
    os.environ["CHROMA_PORT"] = str(settings.chroma_port)
    os.environ["CHROMA_SSL"] = str(settings.chroma_ssl).lower()
    os.environ["CHROMA_TENANT"] = settings.chroma_tenant
    os.environ["CHROMA_DATABASE"] = settings.chroma_database
    os.environ["LLM_TIMEOUT_SECONDS"] = str(settings.llm_timeout_seconds)

    get_embedding_model.cache_clear()
    persist_runtime_settings()
    return get_runtime_settings()
