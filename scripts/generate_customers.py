"""Generate reproducible fictional retail banking customer profiles."""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from faker import Faker

SEED = 4277
OUTPUT_DIR = Path("data/customers")
PRODUCTS = [
    "Current Account",
    "Credit Card",
    "Savings Account Plus",
    "Savings Account Premium",
    "Auto Loan Plus",
    "Personal Loan Flex",
    "Home Mortgage Standard",
    "Student Loan Advantage",
]


def generate_customers(count: int = 50) -> list[dict[str, object]]:
    """Generate fictional customer records."""
    random.seed(SEED)
    Faker.seed(SEED)
    fake = Faker(["en_GB", "fr_FR", "de_DE", "nl_NL", "es_ES", "it_IT"])
    customers: list[dict[str, object]] = []

    for index in range(1, count + 1):
        age = random.randint(19, 78)
        salary = random.choice(
            [
                random.randint(22000, 38000),
                random.randint(39000, 65000),
                random.randint(66000, 115000),
                random.randint(116000, 180000),
            ]
        )
        monthly_expenses = int(random.uniform(0.28, 0.62) * (salary / 12))
        risk_rating = random.choices(["low", "medium", "high"], weights=[48, 38, 14], k=1)[0]
        product_count = random.randint(1, 5)
        existing_products = sorted(random.sample(PRODUCTS, product_count))
        mortgage = "Home Mortgage Standard" in existing_products or random.random() < 0.24
        if mortgage and "Home Mortgage Standard" not in existing_products and random.random() < 0.65:
            existing_products.append("Home Mortgage Standard")
            existing_products = sorted(set(existing_products))

        customer = {
            "customer_id": f"{index:03d}",
            "name": fake.name(),
            "age": age,
            "salary": salary,
            "monthly_expenses": monthly_expenses,
            "risk_rating": risk_rating,
            "existing_products": existing_products,
            "mortgage": mortgage,
            "account_balance": random.randint(500, 85000),
            "customer_since": fake.date_between_dates(
                date_start=date(2008, 1, 1), date_end=date(2024, 12, 31)
            ).isoformat(),
        }
        customers.append(customer)
    return customers


def write_customers(customers: list[dict[str, object]], output_dir: Path = OUTPUT_DIR) -> int:
    """Write one JSON file per customer."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for customer in customers:
        path = output_dir / f"customer_{customer['customer_id']}.json"
        path.write_text(json.dumps(customer, indent=2, ensure_ascii=False))
    return len(customers)


if __name__ == "__main__":
    written = write_customers(generate_customers())
    print(f"Generated {written} customers")
