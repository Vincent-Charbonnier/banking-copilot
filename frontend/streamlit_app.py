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
    raise_for_status_with_detail(response)
    return response.json()


def raise_for_status_with_detail(response: requests.Response) -> None:
    """Raise an HTTP error that includes FastAPI's detail payload when present."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        raise requests.HTTPError(f"{response.status_code} {response.reason}: {detail}") from exc


def api_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    """Call a backend POST endpoint."""
    response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=180)
    raise_for_status_with_detail(response)
    return response.json()


def api_put(path: str, payload: dict[str, Any]) -> Any:
    """Call a backend PUT endpoint."""
    response = requests.put(f"{API_BASE_URL}{path}", json=payload, timeout=30)
    raise_for_status_with_detail(response)
    return response.json()


def render_connection_test(service: str, label: str) -> None:
    """Render a test button and status message for one runtime dependency."""
    if st.button(label, use_container_width=True):
        with st.spinner(f"Testing {service}"):
            result = api_post(f"/settings/test/{service}")
        if result["ok"]:
            st.success(result["message"])
        else:
            st.error(result["message"])


def money(value: int | float) -> str:
    """Format a numeric value as EUR."""
    return f"EUR {value:,.0f}"


def inject_css() -> None:
    """Apply the product UI styling."""
    st.markdown(
        """
        <style>
        :root {
          --ink: #17211d;
          --muted: #66736d;
          --line: #d9dfd8;
          --panel: #ffffff;
          --panel-soft: #f4f7f1;
          --green: #315c48;
          --green-2: #4f7a5f;
          --blue: #285e7b;
          --amber: #a66d1b;
          --red: #9b3f3f;
        }

        html, body, [class*="css"] {
          font-family: 'Aptos', 'SF Pro Display', 'Segoe UI', sans-serif;
        }

        .stApp {
          background:
            linear-gradient(135deg, rgba(49, 92, 72, 0.09), rgba(40, 94, 123, 0.05) 38%, rgba(247, 248, 244, 1) 72%),
            repeating-linear-gradient(0deg, rgba(23, 33, 29, 0.025), rgba(23, 33, 29, 0.025) 1px, transparent 1px, transparent 28px);
          color: var(--ink);
        }

        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding: 1.1rem 1.6rem 2rem; max-width: 1500px; }

        [data-testid="stSidebar"] {
          background: #edf2e9;
          border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
          color: var(--ink);
        }

        .topbar {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 1rem;
          padding: 1rem 0 1.15rem;
          border-bottom: 1px solid rgba(23, 33, 29, 0.12);
          margin-bottom: 1rem;
        }
        .title-block h1 {
          margin: 0;
          font-size: 2rem;
          line-height: 1.1;
          letter-spacing: 0;
          font-weight: 800;
          color: var(--ink);
        }
        .title-block p {
          margin: 0.35rem 0 0;
          color: var(--muted);
          font-size: 0.95rem;
        }
        .status-pill {
          display: inline-flex;
          align-items: center;
          gap: 0.45rem;
          border: 1px solid rgba(49, 92, 72, 0.25);
          border-radius: 999px;
          background: rgba(255,255,255,0.78);
          padding: 0.45rem 0.75rem;
          font-size: 0.82rem;
          color: var(--green);
          white-space: nowrap;
        }
        .status-dot {
          width: 0.55rem;
          height: 0.55rem;
          border-radius: 99px;
          background: #3f8f62;
        }

        .metric-row {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 0.75rem;
          margin: 0.9rem 0 1rem;
        }
        .metric-card {
          background: rgba(255,255,255,0.86);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 0.85rem 0.95rem;
          min-height: 82px;
        }
        .metric-label {
          color: var(--muted);
          font-size: 0.74rem;
          font-weight: 700;
          text-transform: uppercase;
        }
        .metric-value {
          margin-top: 0.35rem;
          font-size: 1.16rem;
          font-weight: 800;
          color: var(--ink);
          overflow-wrap: anywhere;
        }
        .risk-low { color: var(--green); }
        .risk-medium { color: var(--amber); }
        .risk-high { color: var(--red); }

        .section-panel {
          background: rgba(255,255,255,0.88);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 1rem;
        }
        .section-title {
          font-size: 0.86rem;
          font-weight: 800;
          text-transform: uppercase;
          color: #35413b;
          margin-bottom: 0.65rem;
        }
        .subtle {
          color: var(--muted);
          font-size: 0.86rem;
        }
        .product-chip {
          display: inline-block;
          padding: 0.28rem 0.5rem;
          margin: 0.12rem 0.18rem 0.12rem 0;
          border-radius: 999px;
          background: #e9efe5;
          border: 1px solid #d6dfd1;
          font-size: 0.78rem;
          color: #2d3a33;
        }
        .source-chip {
          display: block;
          padding: 0.48rem 0.58rem;
          margin-bottom: 0.35rem;
          border-radius: 7px;
          background: #eef4f6;
          border: 1px solid #d6e5ea;
          color: #26485a;
          font-size: 0.78rem;
        }
        div[data-testid="stChatMessage"] {
          background: rgba(255,255,255,0.75);
          border: 1px solid rgba(217, 223, 216, 0.9);
          border-radius: 8px;
          padding: 0.7rem;
        }
        .stTabs [data-baseweb="tab-list"] {
          gap: 0.25rem;
          border-bottom: 1px solid var(--line);
        }
        .stTabs [data-baseweb="tab"] {
          border-radius: 6px 6px 0 0;
          padding: 0.55rem 0.85rem;
          font-weight: 700;
        }
        @media (max-width: 900px) {
          .metric-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .topbar { flex-direction: column; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(settings: dict[str, Any]) -> None:
    """Render the app header."""
    model = settings.get("llm_model", "not configured")
    chroma_mode = settings.get("chroma_mode", "unknown")
    st.markdown(
        f"""
        <div class="topbar">
          <div class="title-block">
            <h1>Retail Banking Advisor Copilot</h1>
            <p>Advisor workspace for customer analysis, product recommendations, policy evidence, and follow-up drafting.</p>
          </div>
          <div class="status-pill"><span class="status-dot"></span>{model} / Chroma {chroma_mode}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_response_state() -> dict[str, list[Any]]:
    """Return the default empty assistant response state."""
    return {
        "tool_calls": [],
        "retrieved_documents": [],
        "sources": [],
        "suggested_questions": [],
    }


def render_sidebar_customer(customers: list[dict[str, Any]]) -> dict[str, Any]:
    """Render customer selector and profile details."""
    with st.sidebar:
        st.subheader("Portfolio")
        selected_customer = st.selectbox(
            "Customer",
            customers,
            format_func=lambda item: f"{item['customer_id']} - {item['name']}",
        )
        st.divider()
        st.markdown(f"### {selected_customer['name']}")
        st.caption(f"Customer {selected_customer['customer_id']} since {selected_customer['customer_since']}")
        st.markdown(
            "".join(f'<span class="product-chip">{product}</span>' for product in selected_customer["existing_products"]),
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_response = empty_response_state()
            st.rerun()
    return selected_customer


def render_customer_metrics(customer: dict[str, Any]) -> None:
    """Render selected customer summary metrics."""
    risk_class = f"risk-{customer['risk_rating']}"
    st.markdown(
        f"""
        <div class="metric-row">
          <div class="metric-card">
            <div class="metric-label">Annual salary</div>
            <div class="metric-value">{money(customer['salary'])}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Monthly expenses</div>
            <div class="metric-value">{money(customer['monthly_expenses'])}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Risk rating</div>
            <div class="metric-value {risk_class}">{customer['risk_rating'].title()}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Balance</div>
            <div class="metric-value">{money(customer['account_balance'])}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_prompt_suggestions(customer_id: str) -> None:
    """Render context-aware prompt suggestions."""
    response = st.session_state.last_response
    suggestions = response.get("suggested_questions", [])
    if not st.session_state.messages or not suggestions:
        suggestions = [f"Summarize customer {customer_id}"]

    st.markdown('<div class="section-title">Suggested Questions</div>', unsafe_allow_html=True)
    cols = st.columns(min(len(suggestions), 4))
    for index, suggestion in enumerate(suggestions[:4]):
        with cols[index]:
            if st.button(suggestion, use_container_width=True, key=f"suggestion_{index}"):
                st.session_state.pending_prompt = suggestion
                st.rerun()


def run_chat_prompt(prompt: str, selected_customer: dict[str, Any]) -> None:
    """Submit a prompt to the backend and update chat state."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    response = api_post(
        "/chat",
        {
            "message": prompt,
            "customer_id": selected_customer["customer_id"],
            "history": st.session_state.messages[:-1],
        },
    )
    st.session_state.messages.append({"role": "assistant", "content": response["answer"]})
    st.session_state.last_response = response


def render_message_box(selected_customer: dict[str, Any]) -> None:
    """Render the advisor prompt box below the conversation."""
    with st.form("advisor_prompt_form", clear_on_submit=True):
        prompt = st.text_area(
            "Ask the advisor copilot",
            placeholder="Ask about customer needs, products, policies, affordability, or next steps",
            height=88,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Send", use_container_width=True)
    if submitted and prompt.strip():
        with st.spinner("Running advisor tools"):
            run_chat_prompt(prompt.strip(), selected_customer)
        st.rerun()


def render_evidence_panel() -> None:
    """Render tool calls, retrieved documents, and sources."""
    response = st.session_state.last_response
    st.markdown('<div class="section-title">Tool Calls</div>', unsafe_allow_html=True)
    tool_calls = response.get("tool_calls", [])
    if not tool_calls:
        st.caption("No tool calls yet.")
    for call in tool_calls:
        with st.expander(call["name"], expanded=False):
            st.json({"arguments": call["arguments"], "result": call["result"]})

    st.markdown('<div class="section-title">Retrieved Documents</div>', unsafe_allow_html=True)
    docs = response.get("retrieved_documents", [])
    if not docs:
        st.caption("No documents retrieved yet.")
    for doc in docs:
        with st.expander(f"{doc['document_name']} ({doc['document_type']})", expanded=False):
            st.caption(f"Score: {doc.get('score')}")
            st.write(doc["chunk"])

    st.markdown('<div class="section-title">Sources</div>', unsafe_allow_html=True)
    sources = response.get("sources", [])
    if sources:
        for source in sources:
            st.markdown(f'<span class="source-chip">{source}</span>', unsafe_allow_html=True)
    else:
        st.caption("No citations yet.")


def render_advisor_tab(selected_customer: dict[str, Any]) -> None:
    """Render advisor chat and evidence panels."""
    render_customer_metrics(selected_customer)

    pending_prompt = st.session_state.pop("pending_prompt", None)
    if pending_prompt:
        with st.spinner("Running advisor tools"):
            run_chat_prompt(pending_prompt, selected_customer)

    chat_col, evidence_col = st.columns([0.64, 0.36], gap="large")
    with chat_col:
        st.markdown('<div class="section-title">Advisor Conversation</div>', unsafe_allow_html=True)
        for item in st.session_state.messages:
            with st.chat_message(item["role"]):
                st.markdown(item["content"])

        render_message_box(selected_customer)
        render_prompt_suggestions(selected_customer["customer_id"])

    with evidence_col:
        render_evidence_panel()


def render_settings_tab(settings: dict[str, Any]) -> None:
    """Render local runtime settings controls."""
    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown('<div class="section-title">Runtime Configuration</div>', unsafe_allow_html=True)
        with st.form("runtime_settings_form"):
            llm_base_url = st.text_input("LLM endpoint", value=settings["llm_base_url"])
            llm_model = st.text_input("LLM model name", value=settings["llm_model"])
            llm_api_key = st.text_input(
                "LLM token",
                value="",
                type="password",
                placeholder="Leave blank to keep the current token",
            )
            llm_ssl_verify = st.checkbox("Verify LLM TLS certificate", value=bool(settings["llm_ssl_verify"]))
            embedding_model = st.text_input("Embedding model", value=settings["embedding_model"])
            embedding_base_url = st.text_input("Embedding endpoint", value=settings["embedding_base_url"])
            embedding_api_key = st.text_input(
                "Embedding token",
                value="",
                type="password",
                placeholder="Leave blank to keep the current token",
            )
            embedding_ssl_verify = st.checkbox(
                "Verify embedding TLS certificate",
                value=bool(settings["embedding_ssl_verify"]),
            )
            chroma_mode = "http"
            st.caption("ChromaDB is remote-only. Leave it blank until your server endpoint is ready.")
            chroma_host = st.text_input("ChromaDB endpoint or host", value=settings["chroma_host"])
            chroma_port = st.number_input(
                "ChromaDB port",
                min_value=1,
                max_value=65535,
                value=int(settings["chroma_port"]),
                step=1,
            )
            chroma_ssl = st.checkbox("Use SSL for ChromaDB", value=bool(settings["chroma_ssl"]))
            chroma_ssl_verify = st.checkbox("Verify ChromaDB TLS certificate", value=bool(settings["chroma_ssl_verify"]))
            chroma_tenant = st.text_input("ChromaDB tenant", value=settings["chroma_tenant"])
            chroma_database = st.text_input("ChromaDB database", value=settings["chroma_database"])
            llm_timeout_seconds = st.number_input(
                "LLM timeout seconds",
                min_value=1.0,
                max_value=300.0,
                value=float(settings["llm_timeout_seconds"]),
                step=1.0,
            )
            submitted = st.form_submit_button("Save settings", use_container_width=True)

        if submitted:
            payload = {
                "llm_base_url": llm_base_url,
                "llm_model": llm_model,
                "llm_api_key": llm_api_key or None,
                "llm_ssl_verify": llm_ssl_verify,
                "embedding_model": embedding_model,
                "embedding_base_url": embedding_base_url,
                "embedding_api_key": embedding_api_key or None,
                "embedding_ssl_verify": embedding_ssl_verify,
                "chroma_mode": chroma_mode,
                "chroma_host": chroma_host,
                "chroma_port": chroma_port,
                "chroma_ssl": chroma_ssl,
                "chroma_ssl_verify": chroma_ssl_verify,
                "chroma_tenant": chroma_tenant,
                "chroma_database": chroma_database,
                "llm_timeout_seconds": llm_timeout_seconds,
            }
            updated = api_put("/settings", payload)
            st.session_state.runtime_settings = updated
            st.success("Settings saved. They will be reused after backend restarts.")

    with right:
        st.markdown('<div class="section-title">Active Backend State</div>', unsafe_allow_html=True)
        current = st.session_state.get("runtime_settings", settings)
        st.json(
            {
                "llm_base_url": current["llm_base_url"],
                "llm_model": current["llm_model"],
                "llm_api_key_configured": current["llm_api_key_configured"],
                "llm_ssl_verify": current["llm_ssl_verify"],
                "embedding_model": current["embedding_model"],
                "embedding_base_url": current["embedding_base_url"],
                "embedding_api_key_configured": current["embedding_api_key_configured"],
                "embedding_ssl_verify": current["embedding_ssl_verify"],
                "chroma_mode": current["chroma_mode"],
                "chroma_host": current["chroma_host"],
                "chroma_port": current["chroma_port"],
                "chroma_ssl": current["chroma_ssl"],
                "chroma_ssl_verify": current["chroma_ssl_verify"],
                "chroma_tenant": current["chroma_tenant"],
                "chroma_database": current["chroma_database"],
                "llm_timeout_seconds": current["llm_timeout_seconds"],
            }
        )
        st.markdown('<div class="section-title">Connection Tests</div>', unsafe_allow_html=True)
        st.caption("Save settings first, then test the active backend configuration.")
        test_llm_col, test_embedding_col, test_chroma_col = st.columns(3)
        with test_llm_col:
            render_connection_test("llm", "Test LLM")
        with test_embedding_col:
            render_connection_test("embedding", "Test embeddings")
        with test_chroma_col:
            render_connection_test("chroma", "Test ChromaDB")

        st.markdown('<div class="section-title">Index Maintenance</div>', unsafe_allow_html=True)
        if st.button("Reindex documents", use_container_width=True):
            with st.spinner("Rebuilding product and policy indexes"):
                api_post("/reindex")
            st.success("Product and policy indexes rebuilt.")


st.set_page_config(page_title="Retail Banking Advisor Copilot", layout="wide")
inject_css()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_response" not in st.session_state:
    st.session_state.last_response = empty_response_state()

try:
    customers = api_get("/customers")
    runtime_settings = api_get("/settings")
    st.session_state.runtime_settings = runtime_settings
except Exception as exc:
    st.error(f"Backend unavailable at {API_BASE_URL}: {exc}")
    st.stop()

render_header(st.session_state.runtime_settings)
selected = render_sidebar_customer(customers)
if st.session_state.get("selected_customer_id") != selected["customer_id"]:
    st.session_state.selected_customer_id = selected["customer_id"]
    st.session_state.messages = []
    st.session_state.last_response = empty_response_state()
advisor_tab, settings_tab = st.tabs(["Advisor Workspace", "Settings"])

with advisor_tab:
    render_advisor_tab(selected)

with settings_tab:
    render_settings_tab(st.session_state.runtime_settings)
