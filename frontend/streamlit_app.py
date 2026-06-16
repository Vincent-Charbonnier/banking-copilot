"""Streamlit frontend for the Retail Banking Advisor Copilot."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")


def api_get(path: str) -> Any:
    """Call a backend GET endpoint."""
    response = requests.get(f"{API_BASE_URL}{path}", timeout=15)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    """Call a backend POST endpoint."""
    response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=120)
    response.raise_for_status()
    return response.json()


def api_put(path: str, payload: dict[str, Any]) -> Any:
    """Call a backend PUT endpoint."""
    response = requests.put(f"{API_BASE_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def render_sidebar_customer(customers: list[dict[str, Any]]) -> dict[str, Any]:
    """Render customer selector and profile details."""
    with st.sidebar:
        st.header("Customer")
        selected_customer = st.selectbox(
            "Select customer",
            customers,
            format_func=lambda item: f"{item['customer_id']} - {item['name']}",
        )
        st.markdown(f"**{selected_customer['name']}**")
        st.write(f"Salary: EUR {selected_customer['salary']:,}")
        st.write(f"Risk rating: {selected_customer['risk_rating']}")
        st.write("Existing products:")
        for product in selected_customer["existing_products"]:
            st.caption(product)
    return selected_customer


def render_advisor_tab(selected_customer: dict[str, Any]) -> None:
    """Render advisor chat and evidence panels."""
    left, right = st.columns([0.66, 0.34], gap="large")

    with left:
        for item in st.session_state.messages:
            with st.chat_message(item["role"]):
                st.markdown(item["content"])

        prompt = st.chat_input("Ask about this customer, products, policies, or draft an email")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Running advisor tools..."):
                    response = api_post(
                        "/chat",
                        {
                            "message": prompt,
                            "customer_id": selected_customer["customer_id"],
                            "history": st.session_state.messages[:-1],
                        },
                    )
                st.markdown(response["answer"])
            st.session_state.messages.append({"role": "assistant", "content": response["answer"]})
            st.session_state.last_response = response

    with right:
        st.subheader("Tool Calls")
        tool_calls = st.session_state.last_response.get("tool_calls", [])
        if not tool_calls:
            st.caption("No tool calls yet.")
        for call in tool_calls:
            with st.expander(call["name"], expanded=False):
                st.json({"arguments": call["arguments"], "result": call["result"]})

        st.subheader("Retrieved Documents")
        docs = st.session_state.last_response.get("retrieved_documents", [])
        if not docs:
            st.caption("No documents retrieved yet.")
        for doc in docs:
            with st.expander(f"{doc['document_name']} ({doc['document_type']})", expanded=False):
                st.caption(f"Score: {doc.get('score')}")
                st.write(doc["chunk"])

        st.subheader("Sources")
        sources = st.session_state.last_response.get("sources", [])
        if sources:
            for source in sources:
                st.caption(source)
        else:
            st.caption("No citations yet.")


def render_settings_tab(settings: dict[str, Any]) -> None:
    """Render local runtime settings controls."""
    st.subheader("Runtime Settings")

    with st.form("runtime_settings_form"):
        llm_base_url = st.text_input(
            "LLM endpoint",
            value=settings["llm_base_url"],
            help="OpenAI-compatible base URL, for example http://localhost:8000/v1.",
        )
        llm_model = st.text_input("LLM model name", value=settings["llm_model"])
        llm_api_key = st.text_input(
            "LLM token",
            value="",
            type="password",
            placeholder="Leave blank to keep the current token",
            help="The backend stores this only in the current running process.",
        )
        embedding_model = st.text_input(
            "Embedding model",
            value=settings["embedding_model"],
            help="A sentence-transformers model name available to this private environment.",
        )
        chroma_mode = st.segmented_control(
            "ChromaDB access",
            options=["persistent", "http"],
            selection=settings["chroma_mode"],
            help="Use persistent for embedded local storage or http for a separate ChromaDB container/server.",
        ) or settings["chroma_mode"]
        chroma_path = st.text_input(
            "ChromaDB path",
            value=settings["chroma_path"],
            disabled=chroma_mode == "http",
            help="Used only when ChromaDB access is persistent.",
        )
        chroma_host = st.text_input(
            "ChromaDB host",
            value=settings["chroma_host"],
            disabled=chroma_mode == "persistent",
            help="Container DNS name or server hostname, for example chromadb.",
        )
        chroma_port = st.number_input(
            "ChromaDB port",
            min_value=1,
            max_value=65535,
            value=int(settings["chroma_port"]),
            step=1,
            disabled=chroma_mode == "persistent",
        )
        chroma_ssl = st.checkbox(
            "Use SSL for ChromaDB",
            value=bool(settings["chroma_ssl"]),
            disabled=chroma_mode == "persistent",
        )
        chroma_tenant = st.text_input(
            "ChromaDB tenant",
            value=settings["chroma_tenant"],
            disabled=chroma_mode == "persistent",
            help="Usually default_tenant unless your Chroma server is configured otherwise.",
        )
        chroma_database = st.text_input(
            "ChromaDB database",
            value=settings["chroma_database"],
            disabled=chroma_mode == "persistent",
            help="Usually default_database unless your Chroma server is configured otherwise.",
        )
        llm_timeout_seconds = st.number_input(
            "LLM timeout seconds",
            min_value=1.0,
            max_value=300.0,
            value=float(settings["llm_timeout_seconds"]),
            step=1.0,
        )

        submitted = st.form_submit_button("Save runtime settings", use_container_width=True)

    if submitted:
        payload = {
            "llm_base_url": llm_base_url,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key or None,
            "embedding_model": embedding_model,
            "chroma_mode": chroma_mode,
            "chroma_path": chroma_path,
            "chroma_host": chroma_host,
            "chroma_port": chroma_port,
            "chroma_ssl": chroma_ssl,
            "chroma_tenant": chroma_tenant,
            "chroma_database": chroma_database,
            "llm_timeout_seconds": llm_timeout_seconds,
        }
        updated = api_put("/settings", payload)
        st.session_state.runtime_settings = updated
        st.success("Settings updated for this running backend process.")

    current = st.session_state.get("runtime_settings", settings)
    st.markdown("**Current backend configuration**")
    st.json(
        {
            "llm_base_url": current["llm_base_url"],
            "llm_model": current["llm_model"],
            "llm_api_key_configured": current["llm_api_key_configured"],
            "embedding_model": current["embedding_model"],
            "chroma_mode": current["chroma_mode"],
            "chroma_path": current["chroma_path"],
            "chroma_host": current["chroma_host"],
            "chroma_port": current["chroma_port"],
            "chroma_ssl": current["chroma_ssl"],
            "chroma_tenant": current["chroma_tenant"],
            "chroma_database": current["chroma_database"],
            "llm_timeout_seconds": current["llm_timeout_seconds"],
        }
    )

    st.divider()
    st.subheader("Index Maintenance")
    st.write("Rebuild the product and policy ChromaDB collections after changing the embedding model or ChromaDB connection.")
    if st.button("Reindex documents", use_container_width=True):
        with st.spinner("Rebuilding product and policy indexes..."):
            api_post("/reindex")
        st.success("Reindexed product and policy documents.")


st.set_page_config(page_title="Retail Banking Advisor Copilot", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #f7f8f4; color: #202523; }
    [data-testid="stSidebar"] { background: #f0f2ea; border-right: 1px solid #d8ded2; }
    .block-container { padding-top: 1.4rem; }
    .small-label { font-size: 0.78rem; color: #5d685f; text-transform: uppercase; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Retail Banking Advisor Copilot")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_response" not in st.session_state:
    st.session_state.last_response = {"tool_calls": [], "retrieved_documents": [], "sources": []}

try:
    customers = api_get("/customers")
    runtime_settings = api_get("/settings")
    st.session_state.runtime_settings = runtime_settings
except Exception as exc:
    st.error(f"Backend unavailable at {API_BASE_URL}: {exc}")
    st.stop()

selected = render_sidebar_customer(customers)
advisor_tab, settings_tab = st.tabs(["Advisor", "Settings"])

with advisor_tab:
    render_advisor_tab(selected)

with settings_tab:
    render_settings_tab(st.session_state.runtime_settings)
