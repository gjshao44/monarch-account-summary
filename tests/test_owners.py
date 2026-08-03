from datetime import date

import pytest

from monarch_summary.owners import AZS, SSP, OwnersConfig, route_transactions
from monarch_summary.transactions import Transaction


def make_txn(owner, amount=-10.0, category="Restaurants"):
    return Transaction(
        date=date(2026, 1, 1),
        merchant="M",
        category=category,
        account="Acct",
        amount=amount,
        owner=owner,
        notes="",
    )


def default_config(**overrides):
    base = dict(
        azs_names=frozenset({"Alex Test"}),
        ssp_names=frozenset({"Bailey Test"}),
        shared_names=frozenset({"Shared"}),
        shared_split_azs=0.5,
        shared_split_ssp=0.5,
    )
    base.update(overrides)
    return OwnersConfig(**base)


def test_routes_individual_owners():
    result = route_transactions([make_txn("Alex Test"), make_txn("Bailey Test")], default_config())
    assert [r.user for r in result.routed] == [AZS, SSP]


def test_splits_shared_50_50():
    result = route_transactions([make_txn("Shared", amount=-60.0)], default_config())
    assert len(result.routed) == 2
    azs_row = next(r for r in result.routed if r.user == AZS)
    ssp_row = next(r for r in result.routed if r.user == SSP)
    assert azs_row.amount == -30.0
    assert ssp_row.amount == -30.0


def test_custom_split_ratio():
    cfg = default_config(shared_split_azs=0.6, shared_split_ssp=0.4)
    result = route_transactions([make_txn("Shared", amount=-100.0)], cfg)
    azs_row = next(r for r in result.routed if r.user == AZS)
    ssp_row = next(r for r in result.routed if r.user == SSP)
    assert azs_row.amount == pytest.approx(-60.0)
    assert ssp_row.amount == pytest.approx(-40.0)


def test_unrecognized_owner_raises():
    with pytest.raises(ValueError, match="Unknown Person"):
        route_transactions([make_txn("Unknown Person")], default_config())


def test_no_real_names_hardcoded_in_module():
    import monarch_summary.owners as owners_mod

    source = open(owners_mod.__file__).read()
    for banned in ("Andrew", "Sharon", "Shao", "Pan"):
        assert banned not in source
