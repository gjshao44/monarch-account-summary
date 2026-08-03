from datetime import date

from monarch_summary.categorize import apply_categories
from monarch_summary.owners import AZS, RoutedTransaction


def make_routed(category, amount=-10.0):
    return RoutedTransaction(
        user=AZS,
        date=date(2026, 1, 1),
        account="Acct",
        description="M",
        amount=amount,
        category=category,
        notes="",
    )


def test_direct_rename_exclude_and_unmapped():
    mapping = {
        "Restaurants": "Restaurants",
        "Public Transit": "Public Transport",
        "Transfer": None,
    }
    routed = [
        make_routed("Restaurants"),
        make_routed("Public Transit"),
        make_routed("Transfer"),
        make_routed("Weird Category"),
    ]

    result = apply_categories(routed, mapping)

    labels = [r.label for r in result.rows]
    assert labels == ["Restaurants", "Public Transport", None, None]
    assert result.unmapped_categories == {"Weird Category": 1}


def test_null_mapping_not_counted_as_unmapped():
    mapping = {"Transfer": None}
    result = apply_categories([make_routed("Transfer")], mapping)
    assert result.unmapped_categories == {}
    assert result.rows[0].label is None
