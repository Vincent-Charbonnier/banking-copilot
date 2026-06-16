"""Pydantic request and response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Customer(BaseModel):
    """Retail banking customer profile."""

    customer_id: str
    name: str
    age: int
    salary: int
    monthly_expenses: int
    risk_rating: Literal["low", "medium", "high"]
    existing_products: list[str]
    mortgage: bool
    account_balance: int
    customer_since: str


class Interaction(BaseModel):
    """Customer interaction record."""

    customer_id: str
    date: str
    channel: Literal["branch", "phone", "email", "mobile app"]
    summary: str


class ChatMessage(BaseModel):
    """Chat history item."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Chat endpoint request."""

    message: str = Field(..., min_length=1)
    customer_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    """Tool call shown in the API and Streamlit UI."""

    name: str
    arguments: dict[str, Any]
    result: Any


class RetrievedDocument(BaseModel):
    """Retrieved RAG chunk and source metadata."""

    document_type: str
    document_name: str
    chunk: str
    score: float | None = None


class ChatResponse(BaseModel):
    """Chat endpoint response."""

    answer: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class AffordabilityRequest(BaseModel):
    """Affordability input for deterministic checks."""

    annual_salary: int
    monthly_expenses: int
    requested_amount: int


class AffordabilityResult(BaseModel):
    """Deterministic affordability result."""

    status: Literal["approved", "review_required", "not_recommended"]
    score: int
    explanation: str


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str
    app: str


class RuntimeSettings(BaseModel):
    """Runtime settings safe to return to the frontend."""

    llm_base_url: str
    llm_model: str
    llm_api_key_configured: bool
    embedding_model: str
    chroma_mode: Literal["persistent", "http"]
    chroma_path: str
    chroma_host: str
    chroma_port: int
    chroma_ssl: bool
    chroma_tenant: str
    chroma_database: str
    llm_timeout_seconds: float


class RuntimeSettingsUpdate(BaseModel):
    """Runtime settings update from the frontend.

    Empty API keys are ignored so a user can update other fields without
    clearing the current token.
    """

    llm_base_url: str = Field(..., min_length=1)
    llm_model: str = Field(..., min_length=1)
    llm_api_key: str | None = None
    embedding_model: str = Field(..., min_length=1)
    chroma_mode: Literal["persistent", "http"] = "persistent"
    chroma_path: str = Field(..., min_length=1)
    chroma_host: str = Field(default="localhost", min_length=1)
    chroma_port: int = Field(default=8000, gt=0, le=65535)
    chroma_ssl: bool = False
    chroma_tenant: str = Field(default="default_tenant", min_length=1)
    chroma_database: str = Field(default="default_database", min_length=1)
    llm_timeout_seconds: float = Field(default=30, gt=0)
