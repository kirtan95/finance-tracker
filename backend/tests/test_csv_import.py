"""CSV import tests with a small bank-style CSV fixture."""
from __future__ import annotations

import io
from pathlib import Path

SAMPLE_CSV = Path(__file__).with_name("sample_statement.csv").read_text(encoding="utf-8")


def _upload(client, auth_headers, account_id, csv_text=SAMPLE_CSV, **form_overrides):
    form = {
        "account_id": str(account_id),
        "date_column": "Date",
        "description_column": "Description",
        "amount_column": "Amount",
        "category_column": "Category",
        "date_format": "%Y-%m-%d",
    }
    form.update(form_overrides)
    files = {"file": ("statement.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    return client.post("/api/import/csv", data=form, files=files, headers=auth_headers)


def test_csv_import_creates_transactions_and_categories(client, auth_headers, account_id):
    r = _upload(client, auth_headers, account_id)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["imported"] == 5
    assert result["skipped_duplicates"] == 0
    assert result["errors"] == []

    # The negative amounts became expenses, the positive one income.
    r = client.get("/api/transactions?limit=100", headers=auth_headers)
    txns = r.json()
    assert len(txns) == 5
    by_desc = {t["description"]: t for t in txns}
    assert by_desc["ACME Corp Payroll"]["type"] == "income"
    assert by_desc["ACME Corp Payroll"]["amount"] == 2500.00
    assert by_desc["Shell Gas Station"]["type"] == "expense"
    assert by_desc["Netflix"]["amount"] == 15.99

    # Categories from the CSV were created and linked.
    r = client.get("/api/categories", headers=auth_headers)
    names = {c["name"] for c in r.json()}
    assert {"Groceries", "Salary", "Transport", "Entertainment"}.issubset(names)
    assert by_desc["Netflix"]["category_name"] == "Entertainment"


def test_csv_import_is_idempotent(client, auth_headers, account_id):
    r = _upload(client, auth_headers, account_id)
    assert r.json()["imported"] == 5
    # Import the exact same file again: everything is a duplicate.
    r = _upload(client, auth_headers, account_id)
    result = r.json()
    assert result["imported"] == 0
    assert result["skipped_duplicates"] == 5

    # Overlapping file: 1 new row, 1 duplicate.
    overlap = SAMPLE_CSV + "2026-09-12,Chipotle,-12.50,Dining\n"
    r = _upload(client, auth_headers, account_id, csv_text=overlap)
    result = r.json()
    assert result["imported"] == 1
    assert result["skipped_duplicates"] == 5


def test_csv_import_reports_row_errors(client, auth_headers, account_id):
    bad_csv = """Date,Description,Amount
2026-09-01,Good Row,-10.00
not-a-date,Bad Date,-5.00
2026-09-02,Bad Amount,abc
"""
    r = _upload(
        client,
        auth_headers,
        account_id,
        csv_text=bad_csv,
        category_column="",
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["imported"] == 1
    assert len(result["errors"]) == 2
    assert any("Row 3" in e for e in result["errors"])
    assert any("Row 4" in e for e in result["errors"])


def test_csv_import_validates_columns(client, auth_headers, account_id):
    r = _upload(client, auth_headers, account_id, date_column="Nope")
    assert r.status_code == 400
    assert "date_column" in r.json()["detail"]


def test_csv_import_explicit_type_column(client, auth_headers, account_id):
    csv_text = """Posted,Merchant,Value,Kind
09/01/2026,Refund from Store,25.00,CREDIT
09/02/2026,Coffee Shop,4.50,DEBIT
"""
    files = {"file": ("stmt.csv", io.BytesIO(csv_text.encode()), "text/csv")}
    form = {
        "account_id": str(account_id),
        "date_column": "Posted",
        "description_column": "Merchant",
        "amount_column": "Value",
        "type_column": "Kind",
        "date_format": "%m/%d/%Y",
    }
    r = client.post("/api/import/csv", data=form, files=files, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    r = client.get("/api/transactions?limit=100", headers=auth_headers)
    by_desc = {t["description"]: t for t in r.json()}
    assert by_desc["Refund from Store"]["type"] == "income"
    assert by_desc["Coffee Shop"]["type"] == "expense"
