from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import httpx
import chromadb
from typing import List, Dict, Any

app = FastAPI()

# Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")

EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_SSL = os.getenv("CHROMA_SSL", "false").lower() == "true"
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "banking_docs")


class AskRequest(BaseModel):
    question: str
    customer_data: Dict[str, Any]


class AskResponse(BaseModel):
    answer: str


async def get_embedding(text: str) -> List[float]:
    """Generate embedding using external API"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{EMBEDDING_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"},
            json={"input": text, "model": EMBEDDING_MODEL},
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


def query_chromadb(embedding: List[float], n_results: int = 3) -> List[str]:
    """Query ChromaDB for relevant documents"""
    try:
        protocol = "https" if CHROMA_SSL else "http"
        chroma_client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            ssl=CHROMA_SSL
        )
        collection = chroma_client.get_collection(name=CHROMA_COLLECTION)

        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )

        if results and results["documents"]:
            return results["documents"][0]
        return []
    except Exception as e:
        print(f"ChromaDB query error: {e}")
        return []


async def ask_llm(question: str, context: str, customer_data: Dict[str, Any]) -> str:
    """Ask LLM with context"""

    # Format customer data
    customer_info = f"""
Customer: {customer_data['name']}
Account Balance: €{customer_data['balance']:,.2f}
Savings: €{customer_data['savings']:,.2f}
Monthly Spending: €{customer_data['monthly_spending']:,.2f}

Recent Transactions:
"""
    for tx in customer_data.get('transactions', [])[:10]:
        customer_info += f"- {tx['date']}: {tx['merchant']} - €{tx['amount']:,.2f} ({tx['category']})\n"

    system_prompt = f"""You are a helpful banking assistant. Use the customer's data and banking knowledge to answer their questions.

Customer Data:
{customer_info}

Banking Knowledge:
{context}

Provide helpful, accurate, and concise answers about their finances and banking products."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    try:
        # Get embedding for the question
        embedding = await get_embedding(request.question)

        # Query ChromaDB for relevant context
        context_docs = query_chromadb(embedding)
        context = "\n\n".join(context_docs) if context_docs else "No additional context available."

        # Ask LLM
        answer = await ask_llm(request.question, context, request.customer_data)

        return AskResponse(answer=answer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
