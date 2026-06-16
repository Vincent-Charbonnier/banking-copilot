"""Generate reproducible fictional customer interaction histories."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 9413
CUSTOMER_DIR = Path("data/customers")
OUTPUT_DIR = Path("data/interactions")
CHANNELS = ["branch", "phone", "email", "mobile app"]
SUMMARIES = [
    "Customer asked about refinancing options.",
    "Customer requested information about savings rates.",
    "Advisor discussed loan affordability documentation.",
    "Customer queried eligibility for an auto loan.",
    "Customer updated employment and income details.",
    "Customer asked about mortgage overpayment flexibility.",
    "Customer requested a product comparison.",
    "Customer reported planned major purchase.",
    "Advisor explained KYC document requirements.",
    "Customer asked for a follow-up email with next steps.",
    "Customer discussed reducing monthly repayments.",
    "Customer reviewed premium banking eligibility.",
]


def _allocation(customer_count: int, total: int) -> list[int]:
    counts = [3 for _ in range(customer_count)]
    remaining = total - sum(counts)
    positions = list(range(customer_count))
    random.shuffle(positions)
    while remaining > 0:
        changed = False
        for pos in positions:
            if counts[pos] < 15 and remaining > 0:
                counts[pos] += 1
                remaining -= 1
                changed = True
        if not changed:
            raise ValueError("Cannot satisfy interaction total with 3 to 15 interactions per customer")
    return counts


def generate_interactions(total: int = 400) -> int:
    """Generate interaction histories for every customer."""
    random.seed(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    customer_files = sorted(CUSTOMER_DIR.glob("customer_*.json"))
    counts = _allocation(len(customer_files), total)
    start = date(2023, 1, 1)
    end = date(2025, 12, 31)
    total_days = (end - start).days
    written = 0

    for path, count in zip(customer_files, counts, strict=True):
        customer = json.loads(path.read_text())
        customer_id = customer["customer_id"]
        dates = sorted(
            [start + timedelta(days=random.randint(0, total_days)) for _ in range(count)],
            reverse=True,
        )
        interactions = [
            {
                "customer_id": customer_id,
                "date": item_date.isoformat(),
                "channel": random.choice(CHANNELS),
                "summary": random.choice(SUMMARIES),
            }
            for item_date in dates
        ]
        (OUTPUT_DIR / f"interactions_{customer_id}.json").write_text(
            json.dumps(interactions, indent=2, ensure_ascii=False)
        )
        written += len(interactions)
    return written


if __name__ == "__main__":
    print(f"Generated {generate_interactions()} interactions")
