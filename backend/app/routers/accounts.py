"""Account CRUD. Current balance is derived from the starting balance and
all recorded transactions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])


def current_balance(db: Session, account: models.Account) -> float:
    total = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (models.Transaction.type == "income", models.Transaction.amount),
                        (models.Transaction.type == "expense", -models.Transaction.amount),
                        else_=0.0,
                    )
                ),
                0.0,
            )
        )
        .filter(models.Transaction.account_id == account.id)
        .scalar()
    )
    return float(account.starting_balance + (total or 0.0))


def to_out(db: Session, account: models.Account) -> schemas.AccountOut:
    return schemas.AccountOut(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        starting_balance=account.starting_balance,
        current_balance=current_balance(db, account),
    )


@router.get("", response_model=list[schemas.AccountOut])
def list_accounts(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    accounts = (
        db.query(models.Account)
        .filter_by(user_id=current_user.id)
        .order_by(models.Account.name)
        .all()
    )
    return [to_out(db, a) for a in accounts]


@router.post("", response_model=schemas.AccountOut, status_code=201)
def create_account(
    payload: schemas.AccountCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    account = models.Account(
        name=payload.name,
        account_type=payload.account_type,
        starting_balance=payload.starting_balance,
        user_id=current_user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return to_out(db, account)


@router.get("/{account_id}", response_model=schemas.AccountOut)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    account = (
        db.query(models.Account)
        .filter_by(id=account_id, user_id=current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return to_out(db, account)


@router.patch("/{account_id}", response_model=schemas.AccountOut)
def update_account(
    account_id: int,
    payload: schemas.AccountUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    account = (
        db.query(models.Account)
        .filter_by(id=account_id, user_id=current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.name is not None:
        account.name = payload.name
    if payload.account_type is not None:
        account.account_type = payload.account_type
    db.commit()
    db.refresh(account)
    return to_out(db, account)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    account = (
        db.query(models.Account)
        .filter_by(id=account_id, user_id=current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
