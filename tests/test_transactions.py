import pytest

from monarch_summary.transactions import parse_transactions_csv


def test_parse_transactions_csv(fixtures_dir):
    result = parse_transactions_csv(fixtures_dir / "sample_transactions.csv")

    assert result.total_rows == 10
    assert result.skipped_blank_amount == 1
    assert len(result.transactions) == 9

    first = result.transactions[0]
    assert first.date.isoformat() == "2026-01-02"
    assert first.merchant == "Coffee Shop"
    assert first.category == "Restaurants"
    assert first.amount == -12.50
    assert first.owner == "Alex Test"
    assert first.notes == "COFFEE SHOP NYC"


def test_notes_combines_original_statement_and_notes(tmp_path):
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags,Owner,Reviewed\n"
        "1/1/26,M,Restaurants,Acct,ORIGINAL STMT,my note,-5,,Alex Test,Reviewed\n"
    )
    result = parse_transactions_csv(csv_path)
    assert result.transactions[0].notes == "ORIGINAL STMT | my note"


def test_missing_expected_column_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Date,Merchant\n1/1/26,Foo\n")
    with pytest.raises(ValueError, match="missing expected column"):
        parse_transactions_csv(bad)
