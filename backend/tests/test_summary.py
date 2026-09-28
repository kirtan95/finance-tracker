"""Summary endpoint math: category spending, monthly totals, net by account."""
from __future__ import annotations


def _txn(client, headers, account_id, category_id, amount, txn_type, desc, date):
    r = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": amount,
            "type": txn_type,
            "description": desc,
            "date": date,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cat_id(client, headers, name):
    r = client.get("/api/categories", headers=headers)
    return next(c["id"] for c in r.json() if c["name"] == name)


def test_summary_math(client, auth_headers, account_id):
    groceries = _cat_id(client, auth_headers, "Groceries")
    dining = _cat_id(client, auth_headers, "Dining")
    salary = _cat_id(client, auth_headers, "Salary")

    # September
    _txn(client, auth_headers, account_id, groceries, 84.32, "expense", "Whole Foods", "2026-09-01")
    _txn(client, auth_headers, account_id, groceries, 60.00, "expense", "Trader Joes", "2026-09-15")
    _txn(client, auth_headers, account_id, dining, 45.50, "expense", "Chipotle", "2026-09-20")
    _txn(client, auth_headers, account_id, salary, 2500.00, "income", "Paycheck", "2026-09-30")
    # August (previous month, still inside default 6-month window)
    _txn(client, auth_headers, account_id, groceries, 100.00, "expense", "Old Groceries", "2026-08-05")
    _txn(client, auth_headers, account_id, salary, 2500.00, "income", "Old Paycheck", "2026-08-31")

    # Second account: net worth should include both.
    r = client.post(
        "/api/accounts",
        json={"name": "Savings", "account_type": "savings", "starting_balance": 5000},
        headers=auth_headers,
    )
    savings_id = r.json()["id"]

    # Budget for September groceries.
    client.post(
        "/api/budgets",
        json={"category_id": groceries, "month": "2026-09", "amount": 300},
        headers=auth_headers,
    )

    r = client.get("/api/summary?month=2026-09", headers=auth_headers)
    assert r.status_code == 200, r.text
    s = r.json()

    # --- spending by category (expenses only, September) ----------------------
    spending = {c["category_name"]: c["total"] for c in s["spending_by_category"]}
    assert spending["Groceries"] == 144.32
    assert spending["Dining"] == 45.50
    assert "Salary" not in spending  # income excluded

    # --- totals for the target month ------------------------------------------
    assert s["total_income"] == 2500.00
    assert s["total_expenses"] == 189.82
    assert s["net_savings"] == 2310.18

    # --- monthly history includes August ---------------------------------------
    monthly = {m["month"]: m for m in s["monthly_totals"]}
    assert monthly["2026-09"]["income"] == 2500.00
    assert monthly["2026-09"]["expenses"] == 189.82
    assert monthly["2026-08"]["income"] == 2500.00
    assert monthly["2026-08"]["expenses"] == 100.00

    # --- net worth by account ---------------------------------------------------
    nets = {a["account_name"]: a["balance"] for a in s["net_by_account"]}
    # Checking: 1000 start + (5000 income) - (289.82 expenses)
    assert nets["Checking"] == 5710.18
    assert nets["Savings"] == 5000.00

    # --- budget progress ---------------------------------------------------------
    progress = {b["category_name"]: b for b in s["budget_progress"]}
    assert progress["Groceries"]["budgeted"] == 300.00
    assert progress["Groceries"]["spent"] == 144.32
    assert progress["Groceries"]["remaining"] == 155.68


def test_summary_empty_month(client, auth_headers):
    r = client.get("/api/summary?month=2020-01", headers=auth_headers)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["spending_by_category"] == []
    assert s["total_income"] == 0
    assert s["total_expenses"] == 0
    assert s["net_savings"] == 0


def test_summary_rejects_bad_month(client, auth_headers):
    assert client.get("/api/summary?month=sept", headers=auth_headers).status_code == 422
    assert client.get("/api/summary?month=2026-13", headers=auth_headers).status_code == 422
