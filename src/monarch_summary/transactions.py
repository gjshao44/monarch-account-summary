"""Parse a Monarch Money transaction export (CSV) into normalized records."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

# Monarch CSV export columns, in order.
_EXPECTED_HEADER = [
    "Date",
    "Merchant",
    "Category",
    "Account",
    "Original Statement",
    "Notes",
    "Amount",
    "Tags",
    "Owner",
    "Reviewed",
]


@dataclass(frozen=True)
class Transaction:
    date: date
    merchant: str
    category: str
    account: str
    amount: float
    owner: str
    notes: str


@dataclass
class ParseResult:
    transactions: list[Transaction]
    total_rows: int
    skipped_blank_amount: int


_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%y"]


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {raw!r}")


def _build_notes(original_statement: str, notes: str) -> str:
    parts = [p.strip() for p in (original_statement, notes) if p and p.strip()]
    return " | ".join(parts)


def parse_transactions_csv(path: str | Path) -> ParseResult:
    """Parse a Monarch transactions CSV export into normalized Transactions.

    Rows with a blank/missing Amount (pending or not-yet-posted transactions
    in the sample export) are skipped and counted, not silently included as
    zero-dollar spend.
    """
    path = Path(path)
    transactions: list[Transaction] = []
    total_rows = 0
    skipped_blank_amount = 0

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in _EXPECTED_HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"{path}: missing expected column(s) {missing}; "
                f"found columns {reader.fieldnames}"
            )

        for row in reader:
            total_rows += 1
            amount_raw = (row.get("Amount") or "").strip()
            if not amount_raw:
                skipped_blank_amount += 1
                continue

            transactions.append(
                Transaction(
                    date=_parse_date(row["Date"]),
                    merchant=(row.get("Merchant") or "").strip(),
                    category=(row.get("Category") or "").strip(),
                    account=(row.get("Account") or "").strip(),
                    amount=float(amount_raw),
                    owner=(row.get("Owner") or "").strip(),
                    notes=_build_notes(
                        row.get("Original Statement") or "", row.get("Notes") or ""
                    ),
                )
            )

    return ParseResult(
        transactions=transactions,
        total_rows=total_rows,
        skipped_blank_amount=skipped_blank_amount,
    )
