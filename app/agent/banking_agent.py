"""Lightweight tool-calling agent for retail banking advisor workflows."""

from __future__ import annotations

import json
import logging
import re
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

        try:
            llm_response = self._run_llm_tool_loop(message, customer_id, history, tool_records, retrieved_documents)
        except RuntimeError as exc:
            logger.warning("OpenAI tool-calling flow failed; using backend-planned tools with remote LLM: %s", exc)
            tool_records.clear()
            retrieved_documents.clear()
            llm_response = self._run_backend_planned_tool_flow(
                message,
                customer_id,
                history,
                tool_records,
                retrieved_documents,
                str(exc),
            )
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

        for _ in range(6):
            response = self.llm.chat(messages, tools=TOOL_DEFINITIONS)
            choice = response.get("choices", [{}])[0].get("message", {})
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

    def _run_backend_planned_tool_flow(
        self,
        message: str,
        customer_id: str | None,
        history: list[ChatMessage],
        tool_records: list[ToolCallRecord],
        retrieved_documents: list[RetrievedDocument],
        tool_call_error: str,
    ) -> str | None:
        """Execute a deterministic tool plan, then ask the remote LLM to answer normally."""
        lower = message.lower()
        detected_customer_id = self._detect_customer_id(message) or customer_id
        requested_amount = self._detect_amount(message)
        context: dict[str, Any] = {"tool_call_note": f"OpenAI tool-calling request was not accepted: {tool_call_error}"}
        customer: dict[str, Any] | None = None

        if detected_customer_id:
            customer_result = self._execute_tool("get_customer", {"customer_id": detected_customer_id}, tool_records)
            context["customer"] = customer_result
            if isinstance(customer_result, dict) and "error" not in customer_result:
                customer = customer_result
            context["interactions"] = self._execute_tool(
                "get_customer_interactions",
                {"customer_id": detected_customer_id},
                tool_records,
            )

        needs_policy = any(term in lower for term in ["policy", "compliance", "kyc", "suitability", "credit"])
        needs_lending = any(
            term in lower
            for term in ["loan", "mortgage", "recommend", "qualify", "afford", "auto", "car", "personal", "student"]
        )
        needs_product = any(
            term in lower
            for term in ["product", "brochure", "savings", "account", "refinance", "financing", "finance"]
        )
        needs_email = any(term in lower for term in ["email", "follow-up", "follow up"])

        if needs_lending or needs_product:
            product_docs = self._execute_tool("search_products", {"query": message}, tool_records)
            self._collect_retrieved(product_docs, retrieved_documents)
            context["product_documents"] = product_docs

        if needs_lending:
            policy_docs = self._execute_tool("search_policies", {"query": f"affordability approval {message}"}, tool_records)
            self._collect_retrieved(policy_docs, retrieved_documents)
            context["policy_documents"] = policy_docs
            if customer and requested_amount:
                context["affordability"] = self._execute_tool(
                    "calculate_affordability",
                    {
                        "annual_salary": customer["salary"],
                        "monthly_expenses": customer["monthly_expenses"],
                        "requested_amount": requested_amount,
                    },
                    tool_records,
                )

        if needs_policy and not needs_lending:
            policy_docs = self._execute_tool("search_policies", {"query": message}, tool_records)
            self._collect_retrieved(policy_docs, retrieved_documents)
            context["policy_documents"] = policy_docs

        if needs_email and customer:
            recommendation = "follow up on the discussed banking options, subject to suitability and affordability checks."
            context["draft_email"] = self._execute_tool(
                "draft_email",
                {"customer_name": customer["name"], "recommendation": recommendation},
                tool_records,
            )

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append(
            {
                "role": "system",
                "content": (
                    "The backend has already executed the available banking tools. "
                    "Use the JSON context below as grounded evidence. If any tool result contains an error, "
                    "explain what configuration or indexing step is needed instead of inventing facts.\n\n"
                    f"{json.dumps(context, default=str)}"
                ),
            }
        )
        messages.extend(item.model_dump() for item in history[-8:])
        messages.append({"role": "user", "content": message})
        final = self.llm.chat(messages, tools=None)
        return str(final.get("choices", [{}])[0].get("message", {}).get("content") or "").strip() or None

    def _execute_tool(self, name: str, arguments: dict[str, Any], tool_records: list[ToolCallRecord]) -> Any:
        """Execute a backend-planned tool and record errors without aborting chat."""
        try:
            result = self.tools.execute(name, arguments)
        except Exception as exc:
            logger.warning("Backend-planned tool failed: %s %s", name, exc)
            result = {"error": str(exc)}
        tool_records.append(ToolCallRecord(name=name, arguments=arguments, result=result))
        return result

    @staticmethod
    def _detect_customer_id(message: str) -> str | None:
        """Extract a three-digit customer id from a user prompt."""
        match = re.search(r"\bcustomer\s+(\d{1,3})\b|\b(\d{3})\b", message, re.IGNORECASE)
        if not match:
            return None
        return (match.group(1) or match.group(2)).zfill(3)

    @staticmethod
    def _detect_amount(message: str) -> int | None:
        """Extract a requested amount from a user prompt."""
        match = re.search(r"(?:EUR|\u20ac)?\s*(\d{1,3}(?:[,\s]\d{3})+|\d{4,7})", message, re.IGNORECASE)
        if not match:
            return None
        return int(re.sub(r"[,\s]", "", match.group(1)))

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
