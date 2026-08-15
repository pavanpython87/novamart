import random

from src.simulator import chaos_injector as ci


def make_rows(n=100):
    return [{"id": i, "status": "Paid", "amount": 49.99, "notes": "hello",
             "email": "person@example.com", "first_name": "Bob", "last_name": "Smith",
             "date": "2024-05-01"} for i in range(n)]


def test_inject_duplicate_rows_increases_length_close_to_rate():
    rows = make_rows(1000)
    out = ci.inject_duplicate_rows(rows, rate=0.10, rng=random.Random(1))
    assert len(out) > len(rows)
    assert 1050 <= len(out) <= 1200


def test_inject_trailing_whitespace_only_affects_strings():
    rows = make_rows(200)
    out = ci.inject_trailing_whitespace(rows, ["notes"], rate=1.0, rng=random.Random(1))
    assert all(r["notes"].endswith((" ", "\t")) for r in out)


def test_inject_mixed_case_changes_status():
    rows = make_rows(50)
    out = ci.inject_mixed_case(rows, "status", rate=1.0, rng=random.Random(1))
    assert any(r["status"] != "Paid" for r in out)


def test_inject_null_required_fields():
    rows = make_rows(100)
    out = ci.inject_null_required_fields(rows, ["email"], rate=1.0, rng=random.Random(1))
    assert all(r["email"] is None for r in out)


def test_inject_negative_amounts():
    rows = make_rows(100)
    out = ci.inject_negative_amounts(rows, ["amount"], rate=1.0, rng=random.Random(1))
    assert all(r["amount"] < 0 for r in out)


def test_inject_future_dates_sets_future_iso_date():
    import datetime as dt
    rows = make_rows(50)
    out = ci.inject_future_dates(rows, "date", rate=1.0, rng=random.Random(1))
    for r in out:
        assert dt.date.fromisoformat(r["date"]) > dt.date.today()


def test_inject_test_data_replaces_name_and_email():
    rows = make_rows(50)
    out = ci.inject_test_data(rows, ("first_name", "last_name"), "email",
                               rate=1.0, rng=random.Random(1))
    assert all(r["email"] in ci.TEST_DATA_EMAILS for r in out)


def test_inject_currency_symbols_prefixes_amount():
    rows = make_rows(50)
    out = ci.inject_currency_symbols(rows, ["amount"], rate=1.0, rng=random.Random(1))
    assert all(isinstance(r["amount"], str) for r in out)
    assert all(r["amount"][0] in "$UC" for r in out)  # $, USD, or CAD prefix


def test_inject_mixed_date_formats_converts_iso_to_mmddyyyy():
    rows = make_rows(50)
    out = ci.inject_mixed_date_formats(rows, "date", rate=1.0, rng=random.Random(1))
    assert all(r["date"] == "05/01/2024" for r in out)


def test_flip_sign_convention():
    rows = make_rows(50)
    out = ci.flip_sign_convention(rows, ["amount"], rate=1.0, rng=random.Random(1))
    assert all(r["amount"] < 0 for r in out)


def test_inject_html_entities():
    rows = [{"name": "Bob & Sons \"Best\""}]
    out = ci.inject_html_entities(rows, ["name"], rate=1.0, rng=random.Random(1))
    assert "&amp;" in out[0]["name"]
    assert "&quot;" in out[0]["name"]


def test_inject_invisible_chars_increases_length():
    rows = [{"name": "Bob Smith"} for _ in range(20)]
    out = ci.inject_invisible_chars(rows, ["name"], rate=1.0, rng=random.Random(1))
    assert all(len(r["name"]) > len("Bob Smith") for r in out)


def test_add_and_drop_column():
    rows = make_rows(5)
    added = ci.add_unexpected_column(rows, "discount_type", lambda: "percentage")
    assert all(r["discount_type"] == "percentage" for r in added)
    dropped = ci.drop_column(added, "status")
    assert all("status" not in r for r in dropped)


def test_reorder_columns_preserves_data():
    rows = make_rows(5)
    reordered = ci.reorder_columns(rows, rng=random.Random(1))
    assert reordered[0].keys() != rows[0].keys() or list(reordered[0].keys()) != list(rows[0].keys())
    assert {k: v for k, v in reordered[0].items()} == rows[0]


def test_duplicate_truncate_empty_file(tmp_path):
    f = tmp_path / "test.csv"
    f.write_bytes(b"a,b,c\n1,2,3\n4,5,6\n")

    dup = ci.duplicate_file(f, rng=random.Random(1))
    assert dup.exists()
    assert dup.read_bytes() == f.read_bytes()

    original_size = f.stat().st_size
    ci.truncate_file(f, keep_fraction=0.5)
    assert f.stat().st_size < original_size

    ci.empty_file(f)
    assert f.stat().st_size == 0


def test_add_bom(tmp_path):
    f = tmp_path / "bom.csv"
    f.write_text("a,b,c\n", encoding="utf-8")
    ci.add_bom(f)
    assert f.read_bytes().startswith(b"\xef\xbb\xbf")
