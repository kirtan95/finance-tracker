"""End-to-end: register -> login -> auth-protected CRUD on every resource."""
from __future__ import annotations


def test_register_login_and_me(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "kirtan@example.com", "name": "Kirtan Patel", "password": "secret1234"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "kirtan@example.com"

    # Duplicate registration is rejected.
    r = client.post(
        "/api/auth/register",
        json={"email": "kirtan@example.com", "name": "Again", "password": "secret1234"},
    )
    assert r.status_code == 400

    # Login with wrong password fails.
    r = client.post(
        "/api/auth/login", json={"email": "kirtan@example.com", "password": "wrongpass"}
    )
    assert r.status_code == 401

    r = client.post(
        "/api/auth/login", json={"email": "kirtan@example.com", "password": "secret1234"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "Kirtan Patel"


def test_protected_endpoints_require_token(client):
    assert client.get("/api/accounts").status_code == 401
    assert client.get("/api/transactions").status_code == 401
    assert client.get("/api/categories").status_code == 401
    assert client.get("/api/summary").status_code == 401
    # Garbage token is rejected too.
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/api/accounts", headers=bad).status_code == 401


def test_account_crud(client, auth_headers):
    # Create
    r = client.post(
        "/api/accounts",
        json={"name": "Savings", "account_type": "savings", "starting_balance": 5000},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    acct = r.json()
    assert acct["current_balance"] == 5000.0
    acct_id = acct["id"]

    # List
    r = client.get("/api/accounts", headers=auth_headers)
    assert r.status_code == 200
    assert any(a["id"] == acct_id for a in r.json())

    # Update
    r = client.patch(
        f"/api/accounts/{acct_id}", json={"name": "Emergency Fund"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Emergency Fund"

    # Delete
    r = client.delete(f"/api/accounts/{acct_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get(f"/api/accounts/{acct_id}", headers=auth_headers)
    assert r.status_code == 404


def test_transaction_crud_and_balance(client, auth_headers, account_id, category_id):
    payload = {
        "account_id": account_id,
        "category_id": category_id,
        "amount": 42.50,
        "type": "expense",
        "description": "Whole Foods",
        "date": "2026-09-10",
    }
    r = client.post("/api/transactions", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    txn = r.json()
    assert txn["category_name"] == "Groceries"
    assert txn["account_name"] == "Checking"
    txn_id = txn["id"]

    # Balance reflects the expense: 1000 - 42.50
    r = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert r.json()["current_balance"] == 957.50

    # Add income -> 1000 - 42.50 + 2000
    r = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "category_id": None,
            "amount": 2000,
            "type": "income",
            "description": "Paycheck",
            "date": "2026-09-15",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    r = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert r.json()["current_balance"] == 2957.50

    # Filter by type
    r = client.get("/api/transactions?type=income", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["description"] == "Paycheck"

    # Update
    r = client.patch(
        f"/api/transactions/{txn_id}", json={"amount": 50.0}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["amount"] == 50.0

    # Delete
    r = client.delete(f"/api/transactions/{txn_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get(f"/api/transactions/{txn_id}", headers=auth_headers)
    assert r.status_code == 404


def test_category_crud(client, auth_headers):
    # Defaults were seeded at registration.
    r = client.get("/api/categories", headers=auth_headers)
    names = {c["name"] for c in r.json()}
    assert {"Salary", "Groceries", "Housing"}.issubset(names)

    r = client.post("/api/categories", json={"name": "Pets"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    cat_id = r.json()["id"]

    r = client.post("/api/categories", json={"name": "Pets"}, headers=auth_headers)
    assert r.status_code == 400  # duplicate per user

    r = client.delete(f"/api/categories/{cat_id}", headers=auth_headers)
    assert r.status_code == 204


def test_budget_crud_and_spent(client, auth_headers, account_id, category_id):
    r = client.post(
        "/api/budgets",
        json={"category_id": category_id, "month": "2026-09", "amount": 400},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    budget_id = r.json()["id"]
    assert r.json()["spent"] == 0.0

    # Same category+month twice is rejected.
    r = client.post(
        "/api/budgets",
        json={"category_id": category_id, "month": "2026-09", "amount": 100},
        headers=auth_headers,
    )
    assert r.status_code == 400

    # An expense in that category/month shows up as spent.
    client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": 120.0,
            "type": "expense",
            "description": "Trader Joes",
            "date": "2026-09-20",
        },
        headers=auth_headers,
    )
    r = client.get("/api/budgets?month=2026-09", headers=auth_headers)
    assert r.json()[0]["spent"] == 120.0

    r = client.patch(
        f"/api/budgets/{budget_id}", json={"amount": 500}, headers=auth_headers
    )
    assert r.json()["amount"] == 500

    r = client.delete(f"/api/budgets/{budget_id}", headers=auth_headers)
    assert r.status_code == 204


def test_users_cannot_see_each_others_data(client, auth_headers, account_id):
    # Register a second user and try to touch the first user's account.
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "name": "Other", "password": "password123"},
    )
    r = client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "password123"}
    )
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get(f"/api/accounts/{account_id}", headers=other).status_code == 404
    r = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,  # belongs to the first user
            "amount": 10,
            "type": "expense",
            "description": "sneaky",
            "date": "2026-09-01",
        },
        headers=other,
    )
    assert r.status_code == 400
