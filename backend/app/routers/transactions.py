"""Transaction CRUD with optional filters."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _check_account(db: Session, account_id: int, user_id: int) -> models.Account:
    account = db.query(models.Account).filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        raise HTTPException(status_code=400, detail="Account not found")
    return account


def _check_category(
    db: Session, category_id: int | None, user_id: int
) -> models.Category | None:
    if category_id is None:
        return None
    category = db.query(models.Category).filter_by(id=category_id, user_id=user_id).first()
    if category is None:
        raise HTTPException(status_code=400, detail="Category not found")
    return category


def to_out(t: models.Transaction) -> schemas.TransactionOut:
    return schemas.TransactionOut(
        id=t.id,
        account_id=t.account_id,
        category_id=t.category_id,
        amount=t.amount,
        type=t.type,
        description=t.description,
        date=t.date,
        category_name=t.category.name if t.category else None,
        account_name=t.account.name if t.account else None,
    )


@router.get("", response_model=list[schemas.TransactionOut])
def list_transactions(
    account_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    type: str | None = Query(default=None, pattern="^(income|expense)$"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Transaction).filter_by(user_id=current_user.id)
    if account_id is not None:
        q = q.filter_by(account_id=account_id)
    if category_id is not None:
        q = q.filter_by(category_id=category_id)
    if type is not None:
        q = q.filter_by(type=type)
    if start_date is not None:
        q = q.filter(models.Transaction.date >= start_date)
    if end_date is not None:
        q = q.filter(models.Transaction.date <= end_date)
    rows = (
        q.order_by(models.Transaction.date.desc(), models.Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [to_out(t) for t in rows]


@router.post("", response_model=schemas.TransactionOut, status_code=201)
def create_transaction(
    payload: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    _check_account(db, payload.account_id, current_user.id)
    _check_category(db, payload.category_id, current_user.id)
    t = models.Transaction(
        user_id=current_user.id,
        account_id=payload.account_id,
        category_id=payload.category_id,
        amount=payload.amount,
        type=payload.type,
        description=payload.description,
        date=payload.date,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.get("/{transaction_id}", response_model=schemas.TransactionOut)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    t = (
        db.query(models.Transaction)
        .filter_by(id=transaction_id, user_id=current_user.id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return to_out(t)


@router.patch("/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction(
    transaction_id: int,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    t = (
        db.query(models.Transaction)
        .filter_by(id=transaction_id, user_id=current_user.id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if payload.account_id is not None:
        _check_account(db, payload.account_id, current_user.id)
        t.account_id = payload.account_id
    if payload.category_id is not None:
        _check_category(db, payload.category_id, current_user.id)
        t.category_id = payload.category_id
    for field in ("amount", "type", "description", "date"):
        value = getattr(payload, field)
        if value is not None:
            setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    t = (
        db.query(models.Transaction)
        .filter_by(id=transaction_id, user_id=current_user.id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(t)
    db.commit()
