"""OpenAI-compatible chat completions client."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Minimal OpenAI-compatible client for private vLLM deployments."""

    def __init__(self) -> None:
        self.chat_url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Call the configured chat completions endpoint."""
        if not settings.llm_base_url:
            raise RuntimeError("LLM endpoint is not configured. Set it in Settings before chatting.")

        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                response = client.post(self.chat_url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("LLM endpoint unavailable at %s: %s", self.chat_url, exc)
            raise RuntimeError(f"LLM endpoint unavailable: {exc}") from exc
