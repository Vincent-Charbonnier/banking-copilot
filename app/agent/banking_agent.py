"""Lightweight tool-calling agent for retail banking advisor workflows."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agent.llm_client import LLMClient
from app.config.settings import settings
from app.models.schemas import ChatMessage, ChatResponse, RetrievedDocument, ToolCallRecord
from app.tools.banking_tools import TOOL_DEFINITIONS, BankingTools

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Retail Banking Advisor Copilot, an enterprise assistant for retail banking advisors.
Use tools for customer data, product retrieval, policy retrieval, email drafting, and affordability calculations.
Ground recommendations in retrieved sources and deterministic affordability results. Do not invent customer data.
Use concise professional language and cite product or policy document names when relevant.
For customer summary requests, return a detailed advisor briefing with these Markdown sections:
Relationship snapshot, Financial position, Existing products, Recent interactions, Risk and suitability notes,
Opportunities, and Recommended next actions. Use clean bullets and avoid malformed tables."""


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
        suggested_questions = self._suggest_questions(message, customer_id, tool_records, retrieved_documents)
        return ChatResponse(
            answer=llm_response,
            tool_calls=tool_records,
            retrieved_documents=retrieved_documents,
            sources=sources,
            suggested_questions=suggested_questions,
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
        messages.append({"role": "system", "content": f"Configured display currency: {settings.currency}."})
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
        messages.append({"role": "system", "content": f"Configured display currency: {settings.currency}."})
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
        match = re.search(r"(?:EUR|USD|\u20ac|\$)?\s*(\d{1,3}(?:[,\s]\d{3})+|\d{4,7})", message, re.IGNORECASE)
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

    def _suggest_questions(
        self,
        message: str,
        customer_id: str | None,
        tool_records: list[ToolCallRecord],
        retrieved_documents: list[RetrievedDocument],
    ) -> list[str]:
        """Suggest relevant next advisor prompts for the current conversation state."""
        detected_customer_id = self._detect_customer_id(message) or customer_id
        if not detected_customer_id:
            return ["Select a customer and summarize their profile."]

        lower = message.lower()
        tool_names = {record.name for record in tool_records}
        document_types = {document.document_type for document in retrieved_documents}
        customer = self._load_customer_for_suggestions(detected_customer_id)
        suggestions: list[str] = []

        def add(question: str) -> None:
            if question not in suggestions:
                suggestions.append(question)

        if not tool_names:
            add(f"Summarize customer {detected_customer_id}")

        is_summary_turn = "summar" in lower or tool_names.issubset({"get_customer", "get_customer_interactions"})
        is_email_turn = "draft_email" in tool_names or "email" in lower or "follow-up" in lower or "follow up" in lower
        is_policy_turn = "search_policies" in tool_names or "policy" in lower or "compliance" in lower
        is_recommendation_turn = (
            "search_products" in tool_names
            or "calculate_affordability" in tool_names
            or any(term in lower for term in ["recommend", "qualify", "loan", "mortgage", "savings", "product"])
        )

        if is_email_turn:
            add(f"What are the next best actions for customer {detected_customer_id}?")
            add(f"Summarize recent customer interactions for customer {detected_customer_id}.")
            add(f"What compliance checks should be completed for customer {detected_customer_id}?")
            add(f"Which product alternatives should I discuss with customer {detected_customer_id}?")
        elif is_policy_turn and not is_recommendation_turn:
            add(f"Customer {detected_customer_id} wants a {settings.currency} 25,000 car loan. What should I recommend?")
            add(f"Is customer {detected_customer_id} likely to qualify based on affordability?")
            add(f"What documents should I request from customer {detected_customer_id}?")
            add(f"Draft a follow-up email for customer {detected_customer_id}.")
        elif is_recommendation_turn or "product" in document_types or "policy" in document_types:
            add("What lending policy applies to this recommendation?")
            add(f"Compare the retrieved product options for customer {detected_customer_id}.")
            add(f"Draft a follow-up email for customer {detected_customer_id}.")
            add(f"What documents should I request from customer {detected_customer_id}?")
        elif is_summary_turn:
            self._add_profile_driven_suggestions(detected_customer_id, customer, add)
        else:
            self._add_profile_driven_suggestions(detected_customer_id, customer, add)

        add(f"Summarize recent customer interactions for customer {detected_customer_id}.")
        return suggestions[:4]

    def _load_customer_for_suggestions(self, customer_id: str) -> dict[str, Any] | None:
        """Load customer data for local suggestion ranking without failing chat."""
        try:
            customer = self.tools.customers.get_customer(customer_id)
        except Exception as exc:
            logger.debug("Could not load customer %s for suggestions: %s", customer_id, exc)
            return None
        return customer.model_dump()

    @staticmethod
    def _add_profile_driven_suggestions(
        customer_id: str,
        customer: dict[str, Any] | None,
        add: Any,
    ) -> None:
        """Add customer-specific questions after the initial profile summary."""
        if not customer:
            add(f"Customer {customer_id} wants a {settings.currency} 25,000 car loan. What should I recommend?")
            add(f"What policy checks apply before recommending a product to customer {customer_id}?")
            add(f"Draft a follow-up email for customer {customer_id}.")
            return

        products = set(customer.get("existing_products", []))
        salary = int(customer.get("salary", 0))
        balance = int(customer.get("account_balance", 0))
        age = int(customer.get("age", 0))
        risk_rating = str(customer.get("risk_rating", "medium"))

        if "Credit Card" in products and "Auto Loan Plus" not in products:
            add(f"Customer {customer_id} wants a {settings.currency} 25,000 car loan. What should I recommend?")
        if balance >= 10000 and "Savings Account Premium" not in products:
            add(f"Which savings products fit customer {customer_id}?")
        if not customer.get("mortgage") and salary >= 60000 and age >= 28:
            add(f"Is customer {customer_id} a candidate for a home mortgage conversation?")
        if risk_rating == "high":
            add(f"What suitability and compliance checks apply to customer {customer_id}?")
        else:
            add(f"Is customer {customer_id} likely to qualify for an auto loan?")

        add(f"What policy checks apply before recommending a product to customer {customer_id}?")
        add(f"Draft a follow-up email for customer {customer_id}.")

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
