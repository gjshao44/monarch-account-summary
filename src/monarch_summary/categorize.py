"""Map Monarch transaction categories to the budget workbook's Label taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from monarch_summary.owners import RoutedTransaction


@dataclass(frozen=True)
class LedgerRow:
    """One row as it will be written to a Data_AZS / Data_SSP sheet."""

    user: str
    date: object
    account: str
    description: str
    amount: float
    label: str | None  # None => intentionally excluded from every rollup
    notes: str


@dataclass
class CategorizeResult:
    rows: list[LedgerRow]
    unmapped_categories: dict[str, int]  # category not present in config at all


def load_category_map(path: str | Path) -> dict[str, str | None]:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return dict(raw.get("mapping", {}) or {})


def apply_categories(
    routed: list[RoutedTransaction], category_map: dict[str, str | None]
) -> CategorizeResult:
    rows: list[LedgerRow] = []
    unmapped: dict[str, int] = {}

    for txn in routed:
        if txn.category in category_map:
            label = category_map[txn.category]
        else:
            unmapped[txn.category] = unmapped.get(txn.category, 0) + 1
            label = None

        rows.append(
            LedgerRow(
                user=txn.user,
                date=txn.date,
                account=txn.account,
                description=txn.description,
                amount=txn.amount,
                label=label,
                notes=txn.notes,
            )
        )

    return CategorizeResult(rows=rows, unmapped_categories=unmapped)
