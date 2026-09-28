# Finance Tracker

A full-stack personal finance platform: track accounts, categorize transactions,
set monthly budgets, import bank CSV statements, and see it all on a dashboard
with spending breakdowns and income-vs-expense trends.

Built as a portfolio project demonstrating a production-style FastAPI + React
stack: JWT authentication, relational data modeling with SQLAlchemy, idempotent
CSV ingestion, aggregate reporting endpoints, and a Dockerized deployment.

## Architecture

```
┌────────────────────┐        ┌────────────────────┐        ┌───────────────────┐
│  React + Vite SPA  │        │  FastAPI backend   │        │  SQLite (dev) /   │
│                    │ HTTP   │                    │SQLAlchemy│  PostgreSQL (prod)│
│  Dashboard (Chart  │───────▶│  /api/auth         │───────▶ │                   │
│  .js pie + bar)    │  JSON  │  /api/accounts     │        │  users            │
│  Transactions CRUD │◀───────│  /api/transactions │        │  accounts         │
│  Accounts          │  JWT   │  /api/categories   │        │  transactions     │
│  CSV import        │ Bearer │  /api/budgets      │        │  categories       │
│                    │        │  /api/summary      │        │  budgets          │
│  nginx (prod)      │        │  /api/import/csv   │        │                   │
└────────────────────┘        └────────────────────┘        └───────────────────┘
        │                               │
        │  docker compose: frontend ──▶ backend ──▶ db (postgres:16)
        │  local dev:        :5173 ──▶ :8000 (proxy) ──▶ finance.db
```

## Quick start

### Option A — Docker Compose (recommended)

```bash
docker compose up --build
```

- App: http://localhost:3000
- API: http://localhost:8000 (docs at http://localhost:8000/docs)
- Postgres runs in the `db` service with data persisted in the `pgdata` volume.

Set a real JWT secret via the environment before any non-local use:

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") docker compose up --build
```

### Option B — Local development

Backend (Python 3.12+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; defaults work out of the box
uvicorn app.main:app --reload
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the backend,
so no CORS configuration is needed locally. Tables are created automatically on
startup; the database is `finance.db` (SQLite) unless `DATABASE_URL` is set.

To run against Postgres locally instead of SQLite:

```bash
DATABASE_URL=postgresql+psycopg2://finance:finance@localhost:5432/finance uvicorn app.main:app --reload
```

### Running the tests

```bash
cd backend
pytest -q
```

Tests run fully offline against throwaway temp SQLite databases (no server needed)
via FastAPI's `TestClient`, and cover register → login → authenticated CRUD,
CSV import (idempotency, row errors, column validation), and summary math.

## API summary

All endpoints except register/login/health require `Authorization: Bearer <JWT>`.

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register; seeds 10 default categories |
| POST | `/api/auth/login` | Returns `{access_token, token_type}` |
| GET | `/api/auth/me` | Current user |
| GET/POST | `/api/accounts` | List / create accounts (balance is derived) |
| GET/PATCH/DELETE | `/api/accounts/{id}` | Read / rename / delete account |
| GET/POST | `/api/transactions` | List (filterable) / create transactions |
| GET/PATCH/DELETE | `/api/transactions/{id}` | Read / update / delete transaction |
| GET/POST | `/api/categories` | List / create categories |
| DELETE | `/api/categories/{id}` | Delete (transactions keep, uncategorized) |
| GET/POST | `/api/budgets` | List (optional `?month=YYYY-MM`) / create budget |
| PATCH/DELETE | `/api/budgets/{id}` | Update amount / delete budget |
| GET | `/api/summary?month=YYYY-MM` | Spending by category, monthly income vs expenses, net worth by account, budget progress |
| POST | `/api/import/csv` | Import bank CSV (multipart; see below) |
| GET | `/api/health` | Health check |

Transaction list filters: `account_id`, `category_id`, `type=income|expense`,
`start_date`, `end_date`, `limit`, `offset`.

## CSV import

`POST /api/import/csv` accepts multipart form data:

| Field | Required | Description |
|---|---|---|
| `file` | yes | The CSV file |
| `account_id` | yes | Account to import into |
| `date_column` | yes | Header name of the date column |
| `description_column` | yes | Header name of the description column |
| `amount_column` | yes | Header name of the amount column |
| `type_column` | no | Header with income/expense (or credit/debit) per row |
| `category_column` | no | Header with category names (created if missing) |
| `date_format` | no | `strptime` format, default `%Y-%m-%d` (ISO also auto-detected) |

Sample input (`backend/tests/sample_statement.csv`):

```csv
Date,Description,Amount,Category
2026-09-01,Whole Foods Market,-84.32,Groceries
2026-09-03,ACME Corp Payroll,2500.00,Salary
2026-09-05,Shell Gas Station,-45.10,Transport
```

Notes:
- Negative amounts (and `(1,234.56)` bank-style debits) are stored as expenses;
  positives as income, unless `type_column` says otherwise.
- **Duplicate detection:** each row is hashed (`SHA-256` over account, date,
  normalized description, amount, type). Re-importing the same file — or
  overlapping statements — skips already-imported rows, backed by a unique
  database constraint so it is safe under concurrency.
- Bad rows don't abort the import; they're collected and returned in `errors`.

## Design decisions

- **FastAPI + React.** FastAPI gives typed request/response validation (Pydantic),
  automatic OpenAPI docs, and async-ready performance with minimal boilerplate —
  a good fit for a JSON API. React with Vite keeps the frontend fast to build and
  easy to reason about; Chart.js covers the dashboard visualizations without a
  heavy BI dependency.
- **JWT (python-jose) + bcrypt (passlib).** Stateless bearer tokens keep the API
  horizontally scalable — no server-side session store. Passwords are hashed with
  bcrypt (cost factor 12 default); tokens expire after 60 minutes (configurable).
- **SQLite for dev, Postgres for prod via `DATABASE_URL`.** SQLAlchemy makes the
  switch a one-line env change. The one dialect-sensitive query (grouping by
  `YYYY-MM`) is abstracted in `app/utils.py` (`strftime` on SQLite, `to_char` on
  Postgres) so the same code runs on both.
- **Derived balances, not stored balances.** An account's current balance is
  computed as `starting_balance + Σ income − Σ expenses`. This keeps balances
  impossible to drift out of sync with the transaction ledger.
- **Idempotent CSV import.** Bank statements overlap; importing the same file
  twice must not double-count. The `import_hash` unique constraint plus
  per-row skip logic makes re-imports safe, and per-row error collection means
  one malformed row can't fail a 10,000-row statement.
- **Amounts are always positive with a separate `type`.** Storing the direction
  in a `type` column (`income`/`expense`) instead of signed amounts avoids
  sign-convention bugs in aggregation queries.

## Project layout

```
finance-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py            # app factory, router wiring
│   │   ├── config.py          # env-based settings
│   │   ├── database.py        # engine + session
│   │   ├── models.py          # User, Account, Transaction, Category, Budget
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── auth.py            # bcrypt hashing, JWT, current-user dependency
│   │   ├── utils.py           # dialect-aware month grouping
│   │   └── routers/           # auth, accounts, transactions, categories(+budgets), summary, import_csv
│   ├── tests/                 # pytest suite + sample CSV fixture
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api.js             # fetch wrapper, money/date helpers
│   │   ├── auth.jsx           # AuthContext (token in localStorage)
│   │   ├── components/        # Layout, ProtectedRoute
│   │   └── pages/             # Auth, Dashboard, Transactions, Accounts, Import
│   ├── nginx.conf             # serves SPA, proxies /api → backend
│   └── Dockerfile             # multi-stage build → nginx
├── docker-compose.yml
├── LICENSE
└── README.md
```
