from datetime import date

from monarch_summary.categorize import LedgerRow
from monarch_summary.pipeline import summarize_rows


def row(user, day, amount, label):
    return LedgerRow(
        user=user, date=date(2026, 8, day), account="Acct", description="M",
        amount=amount, label=label, notes="",
    )


def test_summarize_nets_positive_amounts_under_a_spend_label():
    # A +$2000 transfer landed under the "Rent" label (e.g. a partner paying
    # their share into the account owner's account) should offset spend, the
    # same way the workbook's SUMIFS does -- not be ignored just because it's
    # positive.
    rows = [
        row("AZS", 1, -3000.0, "Rent"),
        row("AZS", 2, 2000.0, "Rent"),
        row("AZS", 3, -50.0, "Groceries"),
    ]
    summary = summarize_rows(rows, "AZS")
    assert summary["spend"] == 1050.0
    assert summary["spend_by_month"] == {"2026-08": 1050.0}


def test_summarize_income_label_excluded_from_spend():
    rows = [row("AZS", 1, 5000.0, "Income"), row("AZS", 2, -20.0, "Taxi")]
    summary = summarize_rows(rows, "AZS")
    assert summary["income"] == 5000.0
    assert summary["spend"] == 20.0


def test_summarize_null_label_excluded_entirely():
    rows = [row("AZS", 1, -500.0, None)]
    summary = summarize_rows(rows, "AZS")
    assert summary["spend"] == 0.0
    assert summary["spend_by_month"] == {}
