"""Print persisted runtime settings as shell exports for startup scripts."""

from __future__ import annotations

import shlex

from app.config.settings import settings


def main() -> None:
    """Export settings loaded from env plus any persisted runtime override."""
    values = {
        "LLM_BASE_URL": settings.llm_base_url,
        "LLM_MODEL": settings.llm_model,
        "LLM_API_KEY": settings.llm_api_key,
        "LLM_SSL_VERIFY": str(settings.llm_ssl_verify).lower(),
        "EMBEDDING_MODEL": settings.embedding_model,
        "EMBEDDING_BASE_URL": settings.embedding_base_url,
        "EMBEDDING_API_KEY": settings.embedding_api_key,
        "EMBEDDING_SSL_VERIFY": str(settings.embedding_ssl_verify).lower(),
        "CHROMA_MODE": settings.chroma_mode,
        "CHROMA_HOST": settings.chroma_host,
        "CHROMA_PORT": str(settings.chroma_port),
        "CHROMA_SSL": str(settings.chroma_ssl).lower(),
        "CHROMA_SSL_VERIFY": str(settings.chroma_ssl_verify).lower(),
        "CHROMA_TENANT": settings.chroma_tenant,
        "CHROMA_DATABASE": settings.chroma_database,
        "LLM_TIMEOUT_SECONDS": str(settings.llm_timeout_seconds),
        "RUNTIME_SETTINGS_PATH": str(settings.runtime_settings_path),
    }
    for key, value in values.items():
        print(f"export {key}={shlex.quote(value)}")


if __name__ == "__main__":
    main()
