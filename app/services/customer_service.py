"""Customer and interaction file access."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config.settings import settings
from app.models.schemas import Customer, Interaction

logger = logging.getLogger(__name__)


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
