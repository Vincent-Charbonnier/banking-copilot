"""Lightweight tool-calling agent for retail banking advisor workflows."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agent.llm_client import LLMClient
from app.models.schemas import ChatMessage, ChatResponse, RetrievedDocument, ToolCallRecord
from app.tools.banking_tools import TOOL_DEFINITIONS, BankingTools

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Retail Banking Advisor Copilot, an enterprise assistant for retail banking advisors.
Use tools for customer data, product retrieval, policy retrieval, email drafting, and affordability calculations.
Ground recommendations in retrieved sources and deterministic affordability results. Do not invent customer data.
Use concise professional language and cite product or policy document names when relevant."""


class BankingAgent:
    """Simple OpenAI-compatible tool-calling agent."""

    def __init__(self) -> None:
        self.tools = BankingTools()
        self.llm = LLMClient()

    def run(self, message: str, customer_id: str | None, history: list[ChatMessage]) -> ChatResponse:
        """Run the agent for one user message."""
        tool_records: list[ToolCallRecord] = []
        retrieved_documents: list[RetrievedDocument] = []

        llm_response = self._run_llm_tool_loop(message, customer_id, history, tool_records, retrieved_documents)
        if not llm_response:
            raise RuntimeError("LLM returned an empty response.")

        sources = self._sources_from_documents(retrieved_documents)
        return ChatResponse(
            answer=llm_response,
            tool_calls=tool_records,
            retrieved_documents=retrieved_documents,
            sources=sources,
        )

    def _run_llm_tool_loop(
        self,
        message: str,
        customer_id: str | None,
        history: list[ChatMessage],
        tool_records: list[ToolCallRecord],
        retrieved_documents: list[RetrievedDocument],
    ) -> str | None:
        """Run a bounded OpenAI-compatible tool loop."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if customer_id:
            messages.append({"role": "system", "content": f"Selected customer_id: {customer_id}"})
        messages.extend(item.model_dump() for item in history[-8:])
        messages.append({"role": "user", "content": message})

        first = self.llm.chat(messages, tools=TOOL_DEFINITIONS)
        if not first:
            return None
        choice = first.get("choices", [{}])[0].get("message", {})
        tool_calls = choice.get("tool_calls") or []
        if not tool_calls:
            return str(choice.get("content") or "").strip() or None

        messages.append(choice)
        for call in tool_calls[:8]:
            function = call.get("function", {})
            name = function.get("name")
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments)
                result = self.tools.execute(name, arguments)
            except Exception as exc:
                logger.exception("Tool call failed: %s", name)
                result = {"error": str(exc)}
                arguments = {}

            self._collect_retrieved(result, retrieved_documents)
            tool_records.append(ToolCallRecord(name=name, arguments=arguments, result=result))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, default=str),
                }
            )

        final = self.llm.chat(messages, tools=None)
        if not final:
            return None
        return str(final.get("choices", [{}])[0].get("message", {}).get("content") or "").strip() or None

    @staticmethod
    def _collect_retrieved(result: Any, retrieved_documents: list[RetrievedDocument]) -> None:
        if not isinstance(result, list):
            return
        for item in result:
            if isinstance(item, dict) and {"document_type", "document_name", "chunk"}.issubset(item):
                retrieved_documents.append(RetrievedDocument.model_validate(item))

    @staticmethod
    def _sources_from_documents(documents: list[RetrievedDocument]) -> list[str]:
        seen: set[str] = set()
        sources: list[str] = []
        for doc in documents:
            label = f"{doc.document_type}: {doc.document_name}"
            if label not in seen:
                seen.add(label)
                sources.append(label)
        return sources
