"""Generate fictional retail banking policy PDFs."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUTPUT_DIR = Path("data/policies")

POLICIES: list[dict[str, str]] = [
    {
        "name": "Lending Policy",
        "focus": "Affordability must be evidenced using verified income, known commitments, account conduct, and responsible lending thresholds.",
        "approval": "Standard approval requires a satisfactory debt service ratio, no unresolved recent arrears, and adequate disposable income after stressed payment estimates.",
    },
    {
        "name": "KYC Policy",
        "focus": "Customer identity, address, source of funds, and sanctions screening must be completed before onboarding or material credit changes.",
        "approval": "Escalate where documents are inconsistent, expired, or where adverse media or politically exposed person indicators require enhanced due diligence.",
    },
    {
        "name": "Customer Suitability Policy",
        "focus": "Advisors must match products to customer needs, objectives, risk profile, financial capacity, and expected product use.",
        "approval": "Recommendations must record why selected products are suitable and why materially cheaper or lower-risk alternatives were not selected.",
    },
    {
        "name": "Product Recommendation Policy",
        "focus": "Product recommendations must be transparent, explain fees and rates, and avoid unsuitable bundling or pressure selling.",
        "approval": "Where a customer is high risk or vulnerable, provide enhanced explanation and document customer understanding before proceeding.",
    },
    {
        "name": "Consumer Credit Policy",
        "focus": "Consumer credit decisions must apply consistent affordability checks, clear pre-contract information, and fair treatment standards.",
        "approval": "Applications require review when requested borrowing exceeds internal income multiples, disposable income coverage is weak, or the customer has recent missed payments.",
    },
]


def _build_pdf(policy: dict[str, str], output_dir: Path) -> None:
    path = output_dir / f"{policy['name'].replace(' ', '_')}.pdf"
    styles = getSampleStyleSheet()
    story = [Paragraph(policy["name"], styles["Title"]), Spacer(1, 12)]
    sections = {
        "Affordability requirements": policy["focus"],
        "Approval criteria": policy["approval"],
        "Verification requirements": (
            "Verify customer identity, income, employment status, existing commitments, account conduct, and product-specific eligibility evidence. "
            "Documents must be current, legible, and consistent with customer declarations."
        ),
        "Escalation rules": (
            "Escalate to a senior advisor or credit specialist when affordability is borderline, risk rating is high, adverse indicators are present, "
            "or a policy exception would be required."
        ),
        "Compliance guidance": (
            "Keep a clear audit trail of data used, tools consulted, recommendation rationale, customer communications, and final advisor decision. "
            "Do not rely on automated output alone for regulated advice."
        ),
    }
    for title, body in sections.items():
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 10))
    SimpleDocTemplate(str(path), pagesize=A4).build(story)


def generate_policies(output_dir: Path = OUTPUT_DIR) -> int:
    """Generate all fictional policy PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for policy in POLICIES:
        _build_pdf(policy, output_dir)
    return len(POLICIES)


if __name__ == "__main__":
    print(f"Generated {generate_policies()} policy documents")
