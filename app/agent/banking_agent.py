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

        llm_response = self._run_llm_tool_loop(message, customer_id, history, tool_records, retrieved_documents)
        if llm_response:
            sources = self._sources_from_documents(retrieved_documents)
            return ChatResponse(
                answer=llm_response,
                tool_calls=tool_records,
                retrieved_documents=retrieved_documents,
                sources=sources,
            )

        return self._fallback_response(message, customer_id, tool_records, retrieved_documents)

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

    def _fallback_response(
        self,
        message: str,
        customer_id: str | None,
        tool_records: list[ToolCallRecord],
        retrieved_documents: list[RetrievedDocument],
    ) -> ChatResponse:
        """Produce a grounded response without an available LLM endpoint."""
        detected_customer = self._detect_customer_id(message) or customer_id or "001"
        requested_amount = self._detect_amount(message)
        lower = message.lower()

        customer = self._call_tool("get_customer", {"customer_id": detected_customer}, tool_records)
        interactions = self._call_tool(
            "get_customer_interactions", {"customer_id": detected_customer}, tool_records
        )

        answer_parts: list[str] = []
        if "email" in lower or "follow-up" in lower or "follow up" in lower:
            recommendation = self._recommendation_sentence(customer, requested_amount)
            email = self._call_tool(
                "draft_email",
                {"customer_name": customer["name"], "recommendation": recommendation},
                tool_records,
            )
            answer_parts.append(email)
        elif "policy" in lower or "compliance" in lower:
            docs = self._call_tool("search_policies", {"query": message}, tool_records)
            self._collect_retrieved(docs, retrieved_documents)
            answer_parts.append(self._format_policy_answer(docs))
        elif any(term in lower for term in ["loan", "mortgage", "recommend", "qualify", "afford"]):
            query = message
            product_docs = self._call_tool("search_products", {"query": query}, tool_records)
            policy_docs = self._call_tool("search_policies", {"query": f"affordability approval {query}"}, tool_records)
            self._collect_retrieved(product_docs, retrieved_documents)
            self._collect_retrieved(policy_docs, retrieved_documents)
            amount = requested_amount or 25000
            affordability = self._call_tool(
                "calculate_affordability",
                {
                    "annual_salary": customer["salary"],
                    "monthly_expenses": customer["monthly_expenses"],
                    "requested_amount": amount,
                },
                tool_records,
            )
            answer_parts.append(self._format_recommendation(customer, interactions, product_docs, policy_docs, affordability, amount))
        else:
            answer_parts.append(self._format_customer_summary(customer, interactions))

        sources = self._sources_from_documents(retrieved_documents)
        return ChatResponse(
            answer="\n\n".join(answer_parts),
            tool_calls=tool_records,
            retrieved_documents=retrieved_documents,
            sources=sources,
        )

    def _call_tool(self, name: str, arguments: dict[str, Any], tool_records: list[ToolCallRecord]) -> Any:
        result = self.tools.execute(name, arguments)
        tool_records.append(ToolCallRecord(name=name, arguments=arguments, result=result))
        return result

    @staticmethod
    def _detect_customer_id(message: str) -> str | None:
        match = re.search(r"\bcustomer\s+(\d{1,3})\b|\b(\d{3})\b", message, re.IGNORECASE)
        if not match:
            return None
        return (match.group(1) or match.group(2)).zfill(3)

    @staticmethod
    def _detect_amount(message: str) -> int | None:
        match = re.search(r"(?:EUR|\u20ac)?\s*(\d{1,3}(?:[,\s]\d{3})+|\d{4,6})", message, re.IGNORECASE)
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

    @staticmethod
    def _format_customer_summary(customer: dict[str, Any], interactions: list[dict[str, Any]]) -> str:
        products = ", ".join(customer["existing_products"])
        recent = "\n".join(
            f"- {item['date']} via {item['channel']}: {item['summary']}" for item in interactions[:5]
        )
        return (
            f"{customer['name']} (customer {customer['customer_id']}) is {customer['age']} with annual salary "
            f"EUR {customer['salary']:,}, monthly expenses of EUR {customer['monthly_expenses']:,}, "
            f"a {customer['risk_rating']} risk rating, and account balance of EUR {customer['account_balance']:,}. "
            f"Existing products: {products}. Mortgage on file: {customer['mortgage']}.\n\n"
            f"Recent interactions:\n{recent if recent else '- No recent interactions found.'}"
        )

    @staticmethod
    def _format_policy_answer(docs: list[dict[str, Any]]) -> str:
        if not docs:
            return "No relevant policy excerpts were found. Reindex documents and try again."
        lines = ["Relevant policy guidance:"]
        for doc in docs[:4]:
            lines.append(f"- {doc['document_name']}: {doc['chunk'][:450].strip()}")
        return "\n".join(lines)

    def _format_recommendation(
        self,
        customer: dict[str, Any],
        interactions: list[dict[str, Any]],
        product_docs: list[dict[str, Any]],
        policy_docs: list[dict[str, Any]],
        affordability: dict[str, Any],
        amount: int,
    ) -> str:
        product_names = ", ".join(dict.fromkeys(doc["document_name"] for doc in product_docs[:3])) or "matching loan products"
        policy_names = ", ".join(dict.fromkeys(doc["document_name"] for doc in policy_docs[:2])) or "relevant lending policy"
        recent_summary = interactions[0]["summary"] if interactions else "No recent interaction context found."
        return (
            f"For {customer['name']}, a EUR {amount:,} request should be assessed against {product_names}. "
            f"Affordability status is `{affordability['status']}` with score {affordability['score']}/100. "
            f"{affordability['explanation']}\n\n"
            f"Recommendation: {self._recommendation_sentence(customer, amount)} "
            f"Use {policy_names} for affordability, verification, and escalation checks. "
            f"Recent customer context: {recent_summary}"
        )

    @staticmethod
    def _recommendation_sentence(customer: dict[str, Any], requested_amount: int | None) -> str:
        amount_text = f" for EUR {requested_amount:,}" if requested_amount else ""
        if customer["risk_rating"] == "high":
            return f"I recommend a cautious review before making a lending offer{amount_text}, with documentation and escalation checks completed first."
        return f"I recommend progressing with a suitable product option{amount_text}, subject to affordability, eligibility, and suitability checks."
