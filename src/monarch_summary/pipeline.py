"""Shared sync pipeline used by both the CLI and the Streamlit app.

Keeping this as the single entry point means the CLI and the GUI can never
drift apart in behavior -- both just call sync_from_csv()/sync_from_transactions()
and render the result differently.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from monarch_summary.categorize import (
    CategorizeResult,
    LedgerRow,
    apply_categories,
    load_category_map,
)
from monarch_summary.excel_writer import write_ledger
from monarch_summary.owners import load_owners_config, route_transactions
from monarch_summary.transactions import ParseResult, Transaction, parse_transactions_csv

# Labels that are income, not spend -- everything else with a non-null label
# rolls into the workbook's "Spending" total.
NON_SPEND_LABELS = {"Income", "401k"}

USERS = ("AZS", "SSP")


@dataclass
class SyncOutcome:
    dest: Path
    cat_result: CategorizeResult
    summaries: dict[str, dict] = field(default_factory=dict)  # "AZS"/"SSP"/"Combined" -> summary dict
    parse_result: ParseResult | None = None  # None when the source was a live Monarch fetch


def summarize_rows(rows: list[LedgerRow], user: str) -> dict:
    """Recompute per-user spend/income the same way the workbook's own
    SUMIFS-by-label formulas do: every row under a label is netted (not
    just negative amounts), so a refund/reimbursement under a spend label
    correctly offsets spend instead of being ignored.
    """
    user_rows = [r for r in rows if r.user == user]
    spend = -sum(r.amount for r in user_rows if r.label and r.label not in NON_SPEND_LABELS)
    income = sum(r.amount for r in user_rows if r.label == "Income")

    by_month: dict[str, float] = defaultdict(float)
    for r in user_rows:
        if r.label and r.label not in NON_SPEND_LABELS:
            by_month[r.date.strftime("%Y-%m")] += -r.amount

    return {
        "row_count": len(user_rows),
        "spend": spend,
        "income": income,
        "spend_by_month": dict(sorted(by_month.items())),
    }


def _combine_summaries(per_user: dict[str, dict]) -> dict:
    by_month: dict[str, float] = defaultdict(float)
    for summary in per_user.values():
        for month, amount in summary["spend_by_month"].items():
            by_month[month] += amount

    return {
        "row_count": sum(s["row_count"] for s in per_user.values()),
        "spend": sum(s["spend"] for s in per_user.values()),
        "income": sum(s["income"] for s in per_user.values()),
        "spend_by_month": dict(sorted(by_month.items())),
    }


def sync_from_transactions(
    transactions: list[Transaction],
    workbook_path: str | Path,
    owners_config_path: str | Path,
    categories_config_path: str | Path,
    output_path: str | Path | None = None,
    in_place: bool = False,
) -> SyncOutcome:
    owners_config = load_owners_config(owners_config_path)
    route_result = route_transactions(transactions, owners_config)
    category_map = load_category_map(categories_config_path)
    cat_result = apply_categories(route_result.routed, category_map)

    dest = write_ledger(
        cat_result.rows,
        workbook_path=workbook_path,
        output_path=output_path,
        in_place=in_place,
    )

    summaries = {user: summarize_rows(cat_result.rows, user) for user in USERS}
    summaries["Combined"] = _combine_summaries(summaries)

    return SyncOutcome(dest=dest, cat_result=cat_result, summaries=summaries)


def sync_from_csv(
    transactions_csv_path: str | Path,
    workbook_path: str | Path,
    owners_config_path: str | Path,
    categories_config_path: str | Path,
    output_path: str | Path | None = None,
    in_place: bool = False,
) -> SyncOutcome:
    parse_result = parse_transactions_csv(transactions_csv_path)
    outcome = sync_from_transactions(
        parse_result.transactions,
        workbook_path,
        owners_config_path,
        categories_config_path,
        output_path,
        in_place,
    )
    outcome.parse_result = parse_result
    return outcome
