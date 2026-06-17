"""Application settings loaded from environment variables."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Runtime configuration for the demo application."""

    app_name: str = "Retail Banking Advisor Copilot"
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    allow_local_llm_fallback: bool = os.getenv("ALLOW_LOCAL_LLM_FALLBACK", "false").lower() in {"1", "true", "yes"}
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "")
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
    allow_local_embedding_fallback: bool = os.getenv("ALLOW_LOCAL_EMBEDDING_FALLBACK", "false").lower() in {"1", "true", "yes"}
    chroma_mode: Literal["persistent", "http"] = os.getenv("CHROMA_MODE", "http").lower()  # type: ignore[assignment]
    chroma_path: Path = Path(os.getenv("CHROMA_PATH", "./chroma_db"))
    chroma_host: str = os.getenv("CHROMA_HOST", "")
    chroma_port: int = int(os.getenv("CHROMA_PORT", "443"))
    chroma_ssl: bool = os.getenv("CHROMA_SSL", "true").lower() in {"1", "true", "yes"}
    chroma_tenant: str = os.getenv("CHROMA_TENANT", "default_tenant")
    chroma_database: str = os.getenv("CHROMA_DATABASE", "default_database")
    data_path: Path = Path(os.getenv("DATA_PATH", "./data"))
    runtime_settings_path: Path = Path(
        os.getenv("RUNTIME_SETTINGS_PATH", os.getenv("DATA_PATH", "./data") + "/config/runtime_settings.json")
    )
    load_persisted_runtime_settings_on_startup: bool = os.getenv("LOAD_PERSISTED_RUNTIME_SETTINGS", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8080")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    def __post_init__(self) -> None:
        """Overlay persisted runtime settings after environment defaults load."""
        self.normalize_chroma_endpoint()
        if self.load_persisted_runtime_settings_on_startup:
            self.load_persisted_runtime_settings()
        self.normalize_chroma_endpoint()

    def load_persisted_runtime_settings(self) -> None:
        """Load saved runtime settings from disk when present."""
        if not self.runtime_settings_path.exists():
            return

        try:
            payload = json.loads(self.runtime_settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read persisted settings from %s: %s", self.runtime_settings_path, exc)
            return

        self.apply_runtime_dict(payload)
        logger.info("Loaded persisted runtime settings from %s", self.runtime_settings_path)

    def apply_runtime_dict(self, payload: dict[str, object]) -> None:
        """Apply runtime settings from a persisted or API-provided dictionary."""
        if "llm_base_url" in payload:
            self.llm_base_url = str(payload["llm_base_url"]).rstrip("/")
        if "llm_model" in payload:
            self.llm_model = str(payload["llm_model"])
        if "llm_api_key" in payload:
            self.llm_api_key = str(payload["llm_api_key"])
        if "embedding_model" in payload:
            self.embedding_model = str(payload["embedding_model"])
        if "embedding_base_url" in payload:
            self.embedding_base_url = str(payload["embedding_base_url"]).rstrip("/")
        if "embedding_api_key" in payload:
            self.embedding_api_key = str(payload["embedding_api_key"])
        if payload.get("chroma_mode") in {"persistent", "http"}:
            self.chroma_mode = str(payload["chroma_mode"])  # type: ignore[assignment]
        if "chroma_path" in payload:
            self.chroma_path = Path(str(payload["chroma_path"]))
        if "chroma_host" in payload:
            self.chroma_host = str(payload["chroma_host"])
        if "chroma_port" in payload:
            self.chroma_port = int(payload["chroma_port"])
        if "chroma_ssl" in payload:
            self.chroma_ssl = self._parse_bool(payload["chroma_ssl"])
        if "chroma_tenant" in payload:
            self.chroma_tenant = str(payload["chroma_tenant"])
        if "chroma_database" in payload:
            self.chroma_database = str(payload["chroma_database"])
        if "llm_timeout_seconds" in payload:
            self.llm_timeout_seconds = float(payload["llm_timeout_seconds"])

    def normalize_chroma_endpoint(self) -> None:
        """Accept either a Chroma host or a full http(s) URL."""
        parsed = urlparse(self.chroma_host)
        if not parsed.scheme or not parsed.hostname:
            return

        self.chroma_host = parsed.hostname
        self.chroma_ssl = parsed.scheme == "https"
        if parsed.port:
            self.chroma_port = parsed.port
        elif self.chroma_ssl:
            self.chroma_port = 443
        else:
            self.chroma_port = 80

    def as_persisted_dict(self) -> dict[str, str | int | float | bool]:
        """Return runtime settings for durable local storage."""
        return {
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_api_key": self.llm_api_key,
            "embedding_model": self.embedding_model,
            "embedding_base_url": self.embedding_base_url,
            "embedding_api_key": self.embedding_api_key,
            "chroma_mode": self.chroma_mode,
            "chroma_path": str(self.chroma_path),
            "chroma_host": self.chroma_host,
            "chroma_port": self.chroma_port,
            "chroma_ssl": self.chroma_ssl,
            "chroma_tenant": self.chroma_tenant,
            "chroma_database": self.chroma_database,
            "llm_timeout_seconds": self.llm_timeout_seconds,
        }

    @staticmethod
    def _parse_bool(value: object) -> bool:
        """Parse bool-like values from JSON or environment-style strings."""
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes"}

    def as_public_dict(self) -> dict[str, str | int | float | bool]:
        """Return settings safe to show in the UI."""
        return {
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_api_key_configured": bool(self.llm_api_key),
            "embedding_model": self.embedding_model,
            "embedding_base_url": self.embedding_base_url,
            "embedding_api_key_configured": bool(self.embedding_api_key),
            "chroma_mode": self.chroma_mode,
            "chroma_path": str(self.chroma_path),
            "chroma_host": self.chroma_host,
            "chroma_port": self.chroma_port,
            "chroma_ssl": self.chroma_ssl,
            "chroma_tenant": self.chroma_tenant,
            "chroma_database": self.chroma_database,
            "llm_timeout_seconds": self.llm_timeout_seconds,
        }


settings = Settings()
