"""CLI entry point: sync a Monarch CSV export into the budget workbook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from monarch_summary.pipeline import SyncOutcome, sync_from_csv

DEFAULT_OWNERS_CONFIG = Path("config/owners.local.yaml")
DEFAULT_CATEGORIES_CONFIG = Path("config/categories.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monarch-summary")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Sync a Monarch CSV export into the workbook")
    sync.add_argument("--transactions", required=True, help="Path to Monarch transactions CSV export")
    sync.add_argument("--workbook", required=True, help="Path to the budget .xlsx workbook")
    sync.add_argument("--output", default=None, help="Where to save the synced workbook (default: expense_data/output/<name>_synced.xlsx)")
    sync.add_argument("--in-place", action="store_true", help="Overwrite --workbook instead of writing a new file")
    sync.add_argument("--owners-config", default=str(DEFAULT_OWNERS_CONFIG), help="Path to local owners config (gitignored)")
    sync.add_argument("--categories-config", default=str(DEFAULT_CATEGORIES_CONFIG), help="Path to category mapping config")

    return parser


def run_sync(args: argparse.Namespace) -> int:
    outcome = sync_from_csv(
        transactions_csv_path=args.transactions,
        workbook_path=args.workbook,
        owners_config_path=args.owners_config,
        categories_config_path=args.categories_config,
        output_path=args.output,
        in_place=args.in_place,
    )
    _print_summary(outcome)
    return 0


def _print_summary(outcome: SyncOutcome) -> None:
    pr = outcome.parse_result
    if pr is not None:
        print(f"Parsed {pr.total_rows} rows from CSV "
              f"({pr.skipped_blank_amount} skipped: no Amount yet).")

    for user in ("AZS", "SSP", "Combined"):
        summary = outcome.summaries[user]
        label = "Combined (AZS + SSP)" if user == "Combined" else user
        rows_note = f"{summary['row_count']} rows written | " if user != "Combined" else ""
        print(f"\n{label}: {rows_note}"
              f"spend ${summary['spend']:,.2f} | income (from transactions) ${summary['income']:,.2f}")
        for month, amount in summary["spend_by_month"].items():
            print(f"    {month}: ${amount:,.2f}")

    if outcome.cat_result.unmapped_categories:
        print("\nWARNING: categories not found in categories.yaml (excluded from every rollup, add them if that's wrong):")
        for cat, count in sorted(outcome.cat_result.unmapped_categories.items()):
            print(f"    {cat!r} ({count}x)")

    print(
        "\nNote: Gross Income (Monthly_AZS!E5 / Monthly_SSP!E5) is a manual-entry "
        "cell in the template -- it has no formula, since gross salary isn't "
        "derivable from deposit transactions. Fill it in once per person for "
        "Gross Savings % to be meaningful."
    )
    print(f"\nWorkbook written to: {outcome.dest}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sync":
        try:
            return run_sync(args)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
