"""CSV import with configurable column mapping and duplicate detection.

Duplicates are detected per user with a SHA-256 hash over
(account_id, date, description, amount). Re-importing the same file (or
overlapping files) skips already-imported rows, and the unique index on
(user_id, import_hash) makes the import idempotent even under races.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/import", tags=["import"])

MAX_ROWS = 10_000
MAX_ERRORS = 25


def import_hash_for(
    account_id: int, txn_date: date, description: str, amount: float, txn_type: str
) -> str:
    normalized = "|".join(
        [
            str(account_id),
            txn_date.isoformat(),
            re.sub(r"\s+", " ", description.strip().lower()),
            f"{amount:.2f}",
            txn_type,
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_amount(raw: str) -> float:
    """Parse '$1,234.56' / '(12.34)' / '12.34' style amounts.

    Returns a *signed* float: negative for money out. Parenthesised values
    (bank-statement convention for debits) count as negative.
    """
    s = raw.strip()
    if not s:
        raise ValueError("empty amount")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("-"):
        negative = True
        s = s[1:]
    value = float(s)
    return -value if negative else value


def _parse_date(raw: str, date_format: str) -> date:
    s = raw.strip()
    try:
        return datetime.strptime(s, date_format).date()
    except ValueError:
        # Fall back to ISO 8601 (YYYY-MM-DD), the most common export format.
        try:
            return date.fromisoformat(s)
        except ValueError:
            raise ValueError(f"unparseable date {raw!r} (expected {date_format})")


@router.post("/csv", response_model=schemas.CsvImportResult)
def import_csv(
    file: UploadFile = File(..., description="Bank-style CSV file"),
    account_id: int = Form(...),
    date_column: str = Form(...),
    description_column: str = Form(...),
    amount_column: str = Form(...),
    # Optional: explicit 'income'/'expense' (or 'credit'/'debit') per row.
    type_column: str | None = Form(default=None),
    # Optional: category name per row; missing names are created.
    category_column: str | None = Form(default=None),
    date_format: str = Form(default="%Y-%m-%d"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    account = (
        db.query(models.Account)
        .filter_by(id=account_id, user_id=current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=400, detail="Account not found")

    try:
        raw_bytes = file.file.read()
        text = raw_bytes.decode("utf-8-sig")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read uploaded file as UTF-8 CSV")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    required = {
        "date_column": date_column,
        "description_column": description_column,
        "amount_column": amount_column,
    }
    for label, col in required.items():
        if col not in reader.fieldnames:
            raise HTTPException(
                status_code=400, detail=f"{label} {col!r} not found in CSV headers"
            )
    for label, col in (("type_column", type_column), ("category_column", category_column)):
        if col and col not in reader.fieldnames:
            raise HTTPException(
                status_code=400, detail=f"{label} {col!r} not found in CSV headers"
            )

    category_cache: dict[str, models.Category] = {}

    def get_or_create_category(name: str) -> models.Category:
        key = name.strip()
        if key in category_cache:
            return category_cache[key]
        existing = (
            db.query(models.Category).filter_by(user_id=current_user.id, name=key).first()
        )
        if existing is None:
            existing = models.Category(name=key, user_id=current_user.id)
            db.add(existing)
            db.flush()
        category_cache[key] = existing
        return existing

    imported = 0
    skipped = 0
    errors: list[str] = []

    for line_no, row in enumerate(reader, start=2):  # 1-based, header is line 1
        if imported + skipped >= MAX_ROWS:
            errors.append(f"Stopped after {MAX_ROWS} rows.")
            break
        try:
            txn_date = _parse_date(row[date_column], date_format)
            description = (row[description_column] or "").strip()
            signed_amount = _parse_amount(row[amount_column])
            if signed_amount == 0:
                raise ValueError("amount is zero")

            if type_column and row.get(type_column):
                raw_type = row[type_column].strip().lower()
                if raw_type in ("income", "credit", "cr", "deposit"):
                    txn_type = "income"
                elif raw_type in ("expense", "debit", "dr", "withdrawal", "payment"):
                    txn_type = "expense"
                else:
                    raise ValueError(f"unknown type {row[type_column]!r}")
            else:
                txn_type = "income" if signed_amount > 0 else "expense"

            amount = abs(round(signed_amount, 2))

            category = None
            if category_column and row.get(category_column):
                category = get_or_create_category(row[category_column])

            h = import_hash_for(account_id, txn_date, description, amount, txn_type)
            dup = (
                db.query(models.Transaction.id)
                .filter_by(user_id=current_user.id, import_hash=h)
                .first()
            )
            if dup:
                skipped += 1
                continue

            txn = models.Transaction(
                user_id=current_user.id,
                account_id=account_id,
                category_id=category.id if category else None,
                amount=amount,
                type=txn_type,
                description=description,
                date=txn_date,
                import_hash=h,
            )
            db.add(txn)
            imported += 1
        except Exception as exc:  # noqa: BLE001 - report the row, keep going
            if len(errors) < MAX_ERRORS:
                errors.append(f"Row {line_no}: {exc}")
            if len(errors) == MAX_ERRORS:
                errors.append("... (further errors suppressed)")

    db.commit()
    return schemas.CsvImportResult(
        imported=imported, skipped_duplicates=skipped, errors=errors
    )
