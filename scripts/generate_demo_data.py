"""Generate all reproducible fictional demo data."""

from __future__ import annotations

from pathlib import Path

from generate_customers import generate_customers, write_customers
from generate_interactions import generate_interactions
from generate_policies import generate_policies
from generate_products import generate_products

DATA_DIRS = [
    Path("data/customers"),
    Path("data/products"),
    Path("data/policies"),
    Path("data/interactions"),
    Path("chroma_db"),
]


def main() -> None:
    """Create directories and generate all demo data."""
    for directory in DATA_DIRS:
        directory.mkdir(parents=True, exist_ok=True)

    customer_count = write_customers(generate_customers(50))
    product_count = generate_products()
    policy_count = generate_policies()
    interaction_count = generate_interactions(400)

    print("Generated:")
    print(f"- {customer_count} customers")
    print(f"- {product_count} product brochures")
    print(f"- {policy_count} policy documents")
    print(f"- {interaction_count} interactions")


if __name__ == "__main__":
    main()
