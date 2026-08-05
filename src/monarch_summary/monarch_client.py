"""Best-effort live Monarch Money connector.

UNVERIFIED: there is no way to test this against a real Monarch account in
this environment (no login credentials available). It is built from the
`monarchmoney` package's method signatures (login/multi_factor_authenticate/
get_transactions) but its return shape has not been exercised against a live
account. Treat this module as a draft to validate the first time real
credentials are available, not as trusted code -- the tested path is
transactions.parse_transactions_csv() feeding owners.route_transactions()
and categorize.apply_categories(), and this module's only job is to produce
the same Transaction objects so it plugs into that already-tested pipeline.

Known gap: the Monarch CSV export has a per-transaction "Owner" column
(which household member a transaction belongs to). It is not confirmed
whether the live GraphQL API exposes an equivalent per-transaction field --
it may instead be an account-level attribute, or not exposed at all. This
wrapper falls back to using the transaction's account display name as the
`owner` value, so owners.local.yaml's azs/ssp name lists would need to list
account names rather than person names when using this live path. Re-check
this against real API output before relying on it.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from monarchmoney import MonarchMoney

from monarch_summary.transactions import Transaction

DEFAULT_START_DATE = None  # None = library default (recent history)


async def _fetch_transactions_async(
    email: str, password: str, mfa_secret_key: str | None, start_date: str | None, end_date: str | None
) -> list[Transaction]:
    mm = MonarchMoney()
    # use_saved_session=False: a cached session on disk is never validated before
    # use, so a stale/expired one gets silently reused and only fails later with a
    # confusing 401 on the first real API call. Always authenticate fresh with the
    # credentials the user just provided.
    await mm.login(
        email=email,
        password=password,
        mfa_secret_key=mfa_secret_key,
        use_saved_session=False,
        save_session=False,
    )

    raw = await mm.get_transactions(limit=10_000, start_date=start_date, end_date=end_date)
    results = raw.get("allTransactions", {}).get("results", []) if isinstance(raw, dict) else []

    transactions: list[Transaction] = []
    for item in results:
        amount = item.get("amount")
        if amount is None:
            continue

        date_raw = item.get("date")  # expected "YYYY-MM-DD"
        txn_date = datetime.strptime(date_raw, "%Y-%m-%d").date()

        merchant = (item.get("merchant") or {}).get("name") or item.get("plaidName") or ""
        category = (item.get("category") or {}).get("name") or ""
        account = (item.get("account") or {}).get("displayName") or ""
        notes = item.get("notes") or ""

        transactions.append(
            Transaction(
                date=txn_date,
                merchant=merchant,
                category=category,
                account=account,
                amount=float(amount),
                owner=account,  # see module docstring: unverified fallback
                notes=notes,
            )
        )
    return transactions


def fetch_transactions(
    email: str | None = None,
    password: str | None = None,
    mfa_secret_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[Transaction]:
    """Log into Monarch and fetch transactions as normalized Transaction objects.

    Credentials default to MONARCH_EMAIL / MONARCH_PASSWORD / MONARCH_MFA_SECRET
    env vars (e.g. from a gitignored .env file) if not passed explicitly.
    """
    email = email or os.environ.get("MONARCH_EMAIL")
    password = password or os.environ.get("MONARCH_PASSWORD")
    mfa_secret_key = mfa_secret_key or os.environ.get("MONARCH_MFA_SECRET")
    if not email or not password:
        raise ValueError(
            "Monarch credentials missing: set MONARCH_EMAIL / MONARCH_PASSWORD "
            "(e.g. in a local .env file) or pass them explicitly."
        )

    return asyncio.run(
        _fetch_transactions_async(email, password, mfa_secret_key, start_date, end_date)
    )
