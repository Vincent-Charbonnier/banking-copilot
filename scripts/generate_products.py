"""Generate fictional product brochure PDFs."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUTPUT_DIR = Path("data/products")

PRODUCTS: list[dict[str, str]] = [
    {
        "name": "Auto Loan Plus",
        "rate": "Fixed representative APR from 5.9% to 8.4%",
        "eligibility": "Salaried customers aged 21 to 70 with stable income and clean recent arrears history.",
        "terms": "EUR 5,000 to EUR 45,000 over 24 to 72 months.",
        "fees": "No arrangement fee. Early settlement fee capped at 1% where permitted.",
    },
    {
        "name": "Auto Loan Premium",
        "rate": "Preferential fixed APR from 4.7% to 6.8%",
        "eligibility": "Low-risk customers with salary above EUR 60,000 or balances above EUR 25,000.",
        "terms": "EUR 20,000 to EUR 90,000 over 36 to 84 months.",
        "fees": "EUR 99 arrangement fee. Optional payment holiday after 12 successful payments.",
    },
    {
        "name": "Home Mortgage Standard",
        "rate": "Variable or fixed rates from 3.8% depending on loan-to-value.",
        "eligibility": "Residential buyers with verified income, deposit evidence, and satisfactory affordability.",
        "terms": "Up to 30 years. Maximum 85% loan-to-value for standard risk profiles.",
        "fees": "Valuation fee may apply. Product fee from EUR 499.",
    },
    {
        "name": "Home Mortgage Premium",
        "rate": "Discounted fixed rates from 3.3% for eligible premium customers.",
        "eligibility": "Low-risk customers with strong disposable income and maximum 75% loan-to-value.",
        "terms": "Up to 35 years. Offset balance option available.",
        "fees": "Product fee from EUR 799. No overpayment fee up to 10% annually.",
    },
    {
        "name": "Savings Account Plus",
        "rate": "Variable savings rate up to 2.6% AER.",
        "eligibility": "Available to retail customers with a current account.",
        "terms": "Instant access. Minimum opening balance EUR 100.",
        "fees": "No monthly fee.",
    },
    {
        "name": "Savings Account Premium",
        "rate": "Tiered variable rate up to 3.4% AER for balances above EUR 20,000.",
        "eligibility": "Customers with premium relationship status or qualifying balances.",
        "terms": "Two free withdrawals per month. Minimum opening balance EUR 10,000.",
        "fees": "No fee when balance remains above EUR 10,000.",
    },
    {
        "name": "Personal Loan Flex",
        "rate": "Representative APR from 7.2% to 12.9%.",
        "eligibility": "Customers aged 21 to 68 with verified income and acceptable credit conduct.",
        "terms": "EUR 2,000 to EUR 50,000 over 12 to 84 months.",
        "fees": "No arrangement fee. Flexible overpayments allowed.",
    },
    {
        "name": "Student Loan Advantage",
        "rate": "Preferential student APR from 4.9% while in study.",
        "eligibility": "Students aged 18 or over enrolled in an accredited European institution.",
        "terms": "EUR 1,000 to EUR 25,000. Interest-only option during study.",
        "fees": "No arrangement fee. Proof of enrolment required annually.",
    },
]


def _build_pdf(product: dict[str, str], output_dir: Path) -> None:
    path = output_dir / f"{product['name'].replace(' ', '_')}.pdf"
    styles = getSampleStyleSheet()
    story = [Paragraph(product["name"], styles["Title"]), Spacer(1, 12)]
    sections = {
        "Product overview": f"{product['name']} is a fictional retail banking product designed for advisor demonstrations in a private AI environment.",
        "Eligibility criteria": product["eligibility"],
        "Interest rates": product["rate"],
        "Fees": product["fees"],
        "Repayment terms": product["terms"],
        "Benefits": "Clear pricing, advisor-led suitability checks, transparent customer communications, and local servicing.",
        "Example customer scenarios": (
            "A customer with stable income, positive account conduct, and sufficient disposable income may be suitable. "
            "A high-risk customer, recent arrears, or insufficient disposable income should trigger additional review."
        ),
    }
    for title, body in sections.items():
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 10))
    SimpleDocTemplate(str(path), pagesize=A4).build(story)


def generate_products(output_dir: Path = OUTPUT_DIR) -> int:
    """Generate all fictional product PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for product in PRODUCTS:
        _build_pdf(product, output_dir)
    return len(PRODUCTS)


if __name__ == "__main__":
    print(f"Generated {generate_products()} product brochures")
