import streamlit as st
import requests
import os

# Backend URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Banking Copilot", layout="wide")

# Header
st.title("🏦 Banking Dashboard")

# Mock customer data
customer_name = "Sarah Johnson"
account_balance = 12_450.75
savings_balance = 8_320.00
monthly_spending = 2_845.30

# Transactions
transactions = [
    {"date": "2026-09-28", "merchant": "Grocery Store", "amount": -125.40, "category": "Groceries"},
    {"date": "2026-09-27", "merchant": "Gas Station", "amount": -65.00, "category": "Transport"},
    {"date": "2026-09-26", "merchant": "Restaurant", "amount": -85.50, "category": "Dining"},
    {"date": "2026-09-25", "merchant": "Salary Deposit", "amount": 3500.00, "category": "Income"},
    {"date": "2026-09-24", "merchant": "Online Shopping", "amount": -220.00, "category": "Shopping"},
    {"date": "2026-09-23", "merchant": "Pharmacy", "amount": -45.80, "category": "Healthcare"},
    {"date": "2026-09-22", "merchant": "Coffee Shop", "amount": -12.50, "category": "Dining"},
    {"date": "2026-09-20", "merchant": "Utilities", "amount": -180.00, "category": "Bills"},
    {"date": "2026-09-18", "merchant": "Gym Membership", "amount": -55.00, "category": "Fitness"},
    {"date": "2026-09-15", "merchant": "Supermarket", "amount": -156.10, "category": "Groceries"},
]

# Dashboard layout
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Customer", customer_name)

with col2:
    st.metric("Account Balance", f"€{account_balance:,.2f}")

with col3:
    st.metric("Savings", f"€{savings_balance:,.2f}")

with col4:
    st.metric("Monthly Spending", f"€{monthly_spending:,.2f}")

st.divider()

# Transactions table
st.subheader("Recent Transactions")
st.dataframe(transactions, use_container_width=True, hide_index=True)

st.divider()

# Banking Copilot
st.subheader("💬 Ask your Banking Copilot")

question = st.text_input(
    "Ask a question about your finances:",
    placeholder="e.g., How much did I spend this month?",
    label_visibility="collapsed"
)

if st.button("Ask", type="primary"):
    if question:
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/ask",
                    json={
                        "question": question,
                        "customer_data": {
                            "name": customer_name,
                            "balance": account_balance,
                            "savings": savings_balance,
                            "monthly_spending": monthly_spending,
                            "transactions": transactions
                        }
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    answer = response.json().get("answer", "No response")
                    st.success("**Answer:**")
                    st.write(answer)
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                st.error(f"Failed to connect to backend: {str(e)}")
    else:
        st.warning("Please enter a question")
