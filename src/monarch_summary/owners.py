"""Route normalized transactions to household members (AZS / SSP).

The real Monarch "Owner" values (people's names) live only in a local,
gitignored config file (owners.local.yaml) supplied by the caller -- nothing
in this module or the rest of the codebase ever hardcodes a real name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from monarch_summary.transactions import Transaction

AZS = "AZS"
SSP = "SSP"


@dataclass(frozen=True)
class OwnersConfig:
    azs_names: frozenset[str]
    ssp_names: frozenset[str]
    shared_names: frozenset[str]
    shared_split_azs: float
    shared_split_ssp: float


@dataclass(frozen=True)
class RoutedTransaction:
    user: str  # AZS or SSP
    date: object
    account: str
    description: str
    amount: float
    category: str
    notes: str


@dataclass
class RouteResult:
    routed: list[RoutedTransaction]
    unrecognized_owners: dict[str, int]  # owner value -> occurrence count


def load_owners_config(path: str | Path) -> OwnersConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Copy config/owners.example.yaml to "
            f"{path.name} next to it and fill in your real Monarch Owner "
            f"values (that file is gitignored, so this is safe to do locally)."
        )
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    split = raw.get("shared_split", {}) or {}
    return OwnersConfig(
        azs_names=frozenset(raw.get("azs", {}).get("monarch_owner_names", []) or []),
        ssp_names=frozenset(raw.get("ssp", {}).get("monarch_owner_names", []) or []),
        shared_names=frozenset(raw.get("shared_owner_names", []) or []),
        shared_split_azs=float(split.get("azs", 0.5)),
        shared_split_ssp=float(split.get("ssp", 0.5)),
    )


def route_transactions(
    transactions: list[Transaction], config: OwnersConfig
) -> RouteResult:
    routed: list[RoutedTransaction] = []
    unrecognized: dict[str, int] = {}

    for txn in transactions:
        if txn.owner in config.azs_names:
            routed.append(_to_routed(AZS, txn, txn.amount, txn.notes))
        elif txn.owner in config.ssp_names:
            routed.append(_to_routed(SSP, txn, txn.amount, txn.notes))
        elif txn.owner in config.shared_names:
            split_note = (
                f"shared, split {config.shared_split_azs:.0%}/"
                f"{config.shared_split_ssp:.0%} of {txn.amount:.2f}"
            )
            notes = f"{txn.notes} | {split_note}" if txn.notes else split_note
            routed.append(
                _to_routed(AZS, txn, txn.amount * config.shared_split_azs, notes)
            )
            routed.append(
                _to_routed(SSP, txn, txn.amount * config.shared_split_ssp, notes)
            )
        else:
            unrecognized[txn.owner] = unrecognized.get(txn.owner, 0) + 1

    if unrecognized:
        details = ", ".join(f"{name!r} ({count}x)" for name, count in unrecognized.items())
        raise ValueError(
            "Unrecognized Owner value(s) in transaction export, not covered by "
            f"owners.local.yaml: {details}. Add them to azs/ssp/shared_owner_names "
            "or fix the mismatch, then re-run."
        )

    return RouteResult(routed=routed, unrecognized_owners=unrecognized)


def _to_routed(
    user: str, txn: Transaction, amount: float, notes: str
) -> RoutedTransaction:
    return RoutedTransaction(
        user=user,
        date=txn.date,
        account=txn.account,
        description=txn.merchant,
        amount=amount,
        category=txn.category,
        notes=notes,
    )
