"""Deterministic local tools used by the banking advisor agent."""

from __future__ import annotations

import logging
from typing import Any

from app.models.schemas import AffordabilityResult
from app.rag.vector_store import VectorStore
from app.services.customer_service import CustomerService

logger = logging.getLogger(__name__)


class BankingTools:
    """Tool implementations for customer, RAG, email, and affordability operations."""

    def __init__(self) -> None:
        self.customers = CustomerService()
        self._vector_store: VectorStore | None = None

    @property
    def vector_store(self) -> VectorStore:
        """Create the ChromaDB client only when a RAG tool is used."""
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Return a customer profile as a JSON-serializable dictionary."""
        return self.customers.get_customer(customer_id).model_dump()

    def get_customer_interactions(self, customer_id: str) -> list[dict[str, Any]]:
        """Return recent customer interactions."""
        return [item.model_dump() for item in self.customers.get_interactions(customer_id)]

    def search_products(self, query: str) -> list[dict[str, Any]]:
        """Search generated product brochures."""
        return [item.model_dump() for item in self.vector_store.search("products", query)]

    def search_policies(self, query: str) -> list[dict[str, Any]]:
        """Search generated policy documents."""
        return [item.model_dump() for item in self.vector_store.search("policies", query)]

    def draft_email(self, customer_name: str, recommendation: str) -> str:
        """Draft a professional follow-up email from provided recommendation context."""
        return (
            f"Subject: Follow-up on your banking options\n\n"
            f"Dear {customer_name},\n\n"
            "Thank you for speaking with us. Based on the information discussed, "
            f"{recommendation}\n\n"
            "The next step is to confirm your current income, monthly commitments, "
            "and any supporting documents required for suitability and affordability checks.\n\n"
            "Please let us know a convenient time to continue.\n\n"
            "Kind regards,\n"
            "Retail Banking Advisory Team"
        )

    def calculate_affordability(
        self,
        annual_salary: int,
        monthly_expenses: int,
        requested_amount: int,
    ) -> dict[str, Any]:
        """Return deterministic affordability using disposable income and loan size."""
        monthly_income = annual_salary / 12
        disposable_income = monthly_income - monthly_expenses
        estimated_payment = requested_amount / 48
        debt_service_ratio = estimated_payment / max(monthly_income, 1)
        disposable_coverage = disposable_income / max(estimated_payment, 1)

        score = 100
        if disposable_income < 600:
            score -= 35
        if debt_service_ratio > 0.22:
            score -= 30
        elif debt_service_ratio > 0.15:
            score -= 15
        if disposable_coverage < 1.5:
            score -= 25
        elif disposable_coverage < 2.5:
            score -= 10
        if requested_amount > annual_salary * 0.8:
            score -= 20
        score = max(0, min(100, round(score)))

        if score >= 75:
            status = "approved"
        elif score >= 50:
            status = "review_required"
        else:
            status = "not_recommended"

        result = AffordabilityResult(
            status=status,
            score=score,
            explanation=(
                f"Estimated monthly payment is EUR {estimated_payment:,.0f}. "
                f"Disposable monthly income is EUR {disposable_income:,.0f}. "
                f"Debt service ratio is {debt_service_ratio:.1%}."
            ),
        )
        return result.model_dump()

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a named tool."""
        tool = getattr(self, name, None)
        if tool is None or not callable(tool):
            raise ValueError(f"Unknown tool: {name}")
        logger.info("Executing tool %s with arguments %s", name, arguments)
        return tool(**arguments)


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_customer",
            "description": "Return a retail banking customer profile.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_interactions",
            "description": "Return recent customer interactions.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search product brochures using RAG.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policies",
            "description": "Search policy documents using RAG.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "Draft a professional customer follow-up email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["customer_name", "recommendation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_affordability",
            "description": "Calculate deterministic loan affordability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "annual_salary": {"type": "integer"},
                    "monthly_expenses": {"type": "integer"},
                    "requested_amount": {"type": "integer"},
                },
                "required": ["annual_salary", "monthly_expenses", "requested_amount"],
            },
        },
    },
]
