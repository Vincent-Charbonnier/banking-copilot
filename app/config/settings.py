"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    """Runtime configuration for the demo application."""

    app_name: str = "Retail Banking Advisor Copilot"
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
    llm_model: str = os.getenv("LLM_MODEL", "qwen3-32b")
    llm_api_key: str = os.getenv("LLM_API_KEY", "local")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    chroma_mode: Literal["persistent", "http"] = os.getenv("CHROMA_MODE", "persistent").lower()  # type: ignore[assignment]
    chroma_path: Path = Path(os.getenv("CHROMA_PATH", "./chroma_db"))
    chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
    chroma_port: int = int(os.getenv("CHROMA_PORT", "8000"))
    chroma_ssl: bool = os.getenv("CHROMA_SSL", "false").lower() in {"1", "true", "yes"}
    chroma_tenant: str = os.getenv("CHROMA_TENANT", "default_tenant")
    chroma_database: str = os.getenv("CHROMA_DATABASE", "default_database")
    data_path: Path = Path(os.getenv("DATA_PATH", "./data"))
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8080")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    def as_public_dict(self) -> dict[str, str | float | bool]:
        """Return settings safe to show in the UI."""
        return {
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_api_key_configured": bool(self.llm_api_key),
            "embedding_model": self.embedding_model,
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
