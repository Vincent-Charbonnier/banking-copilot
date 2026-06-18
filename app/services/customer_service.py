"""Customer and interaction file access."""

from __future__ import annotations

import json
import logging
import random
from datetime import date
from pathlib import Path

from faker import Faker

from app.config.settings import settings
from app.models.schemas import Customer, Interaction

logger = logging.getLogger(__name__)

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


class CustomerService:
    """Reads fictional customer profiles and interactions from local JSON files."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or settings.data_path
        self.customer_path = self.data_path / "customers"
        self.interaction_path = self.data_path / "interactions"

    def list_customers(self) -> list[Customer]:
        """Return all customer profiles sorted by customer ID."""
        customers: list[Customer] = []
        for path in sorted(self.customer_path.glob("customer_*.json")):
            try:
                customers.append(Customer.model_validate_json(path.read_text()))
            except Exception as exc:
                logger.warning("Skipping invalid customer file %s: %s", path, exc)
        return customers

    def next_customer_id(self) -> str:
        """Return the next available three-digit customer ID."""
        max_id = 0
        for customer in self.list_customers():
            if customer.customer_id.isdigit():
                max_id = max(max_id, int(customer.customer_id))
        return f"{max_id + 1:03d}"

    def get_customer(self, customer_id: str) -> Customer:
        """Return one customer profile."""
        normalized_id = customer_id.zfill(3)
        path = self.customer_path / f"customer_{normalized_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Customer {normalized_id} was not found")
        return Customer.model_validate_json(path.read_text())

    def get_interactions(self, customer_id: str) -> list[Interaction]:
        """Return recent interactions for a customer, newest first."""
        normalized_id = customer_id.zfill(3)
        path = self.interaction_path / f"interactions_{normalized_id}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        interactions = [Interaction.model_validate(item) for item in data]
        return sorted(interactions, key=lambda item: item.date, reverse=True)

    def create_customer(self, customer: Customer) -> Customer:
        """Persist a new customer JSON file and initialize empty interactions."""
        normalized_customer = customer.model_copy(update={"customer_id": customer.customer_id.zfill(3)})
        self.customer_path.mkdir(parents=True, exist_ok=True)
        self.interaction_path.mkdir(parents=True, exist_ok=True)

        path = self.customer_path / f"customer_{normalized_customer.customer_id}.json"
        if path.exists():
            raise FileExistsError(f"Customer {normalized_customer.customer_id} already exists")

        path.write_text(normalized_customer.model_dump_json(indent=2), encoding="utf-8")
        interaction_file = self.interaction_path / f"interactions_{normalized_customer.customer_id}.json"
        if not interaction_file.exists():
            interaction_file.write_text("[]", encoding="utf-8")
        logger.info("Created customer profile %s", path)
        return normalized_customer

    def generate_demo_customer(self) -> Customer:
        """Generate one fictional customer profile for form prefill."""
        fake = Faker(["en_GB", "fr_FR", "de_DE", "nl_NL", "es_ES", "it_IT"])
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
        existing_products = sorted(random.sample(PRODUCTS, random.randint(1, 5)))
        mortgage = "Home Mortgage Standard" in existing_products or random.random() < 0.24
        if mortgage and "Home Mortgage Standard" not in existing_products:
            existing_products = sorted({*existing_products, "Home Mortgage Standard"})

        return Customer(
            customer_id=self.next_customer_id(),
            name=fake.name(),
            age=age,
            salary=salary,
            monthly_expenses=monthly_expenses,
            risk_rating=random.choices(["low", "medium", "high"], weights=[48, 38, 14], k=1)[0],
            existing_products=existing_products,
            mortgage=mortgage,
            account_balance=random.randint(500, 85000),
            customer_since=fake.date_between_dates(
                date_start=date(2008, 1, 1),
                date_end=date.today(),
            ).isoformat(),
        )
