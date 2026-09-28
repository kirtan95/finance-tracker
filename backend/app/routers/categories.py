"""Category and budget CRUD."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db
from ..utils import month_expr_for

router = APIRouter(tags=["categories", "budgets"])


# --------------------------------------------------------------- categories
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.Category)
        .filter_by(user_id=current_user.id)
        .order_by(models.Category.name)
        .all()
    )


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be blank")
    existing = (
        db.query(models.Category).filter_by(user_id=current_user.id, name=name).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Category already exists"
        )
    category = models.Category(name=name, user_id=current_user.id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    category = (
        db.query(models.Category)
        .filter_by(id=category_id, user_id=current_user.id)
        .first()
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    # Keep transactions; just clear the reference.
    db.query(models.Transaction).filter_by(category_id=category_id).update(
        {"category_id": None}
    )
    db.delete(category)
    db.commit()


# ----------------------------------------------------------------- budgets
def _month_spent(db: Session, user_id: int, category_id: int, month: str) -> float:
    spent = (
        db.query(func.coalesce(func.sum(models.Transaction.amount), 0.0))
        .filter(
            models.Transaction.user_id == user_id,
            models.Transaction.category_id == category_id,
            models.Transaction.type == "expense",
            month_expr_for(db, models.Transaction.date) == month,
        )
        .scalar()
    )
    return float(spent or 0.0)


def to_budget_out(db: Session, b: models.Budget) -> schemas.BudgetOut:
    return schemas.BudgetOut(
        id=b.id,
        category_id=b.category_id,
        month=b.month,
        amount=b.amount,
        category_name=b.category.name if b.category else "",
        spent=_month_spent(db, b.user_id, b.category_id, b.month),
    )


@router.get("/budgets", response_model=list[schemas.BudgetOut])
def list_budgets(
    month: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Budget).filter_by(user_id=current_user.id)
    if month is not None:
        q = q.filter_by(month=month)
    return [to_budget_out(db, b) for b in q.order_by(models.Budget.month.desc()).all()]


@router.post("/budgets", response_model=schemas.BudgetOut, status_code=201)
def create_budget(
    payload: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    category = (
        db.query(models.Category)
        .filter_by(id=payload.category_id, user_id=current_user.id)
        .first()
    )
    if category is None:
        raise HTTPException(status_code=400, detail="Category not found")
    existing = (
        db.query(models.Budget)
        .filter_by(
            user_id=current_user.id,
            category_id=payload.category_id,
            month=payload.month,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget already exists for this category and month",
        )
    budget = models.Budget(
        user_id=current_user.id,
        category_id=payload.category_id,
        month=payload.month,
        amount=payload.amount,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return to_budget_out(db, budget)


@router.patch("/budgets/{budget_id}", response_model=schemas.BudgetOut)
def update_budget(
    budget_id: int,
    payload: schemas.BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    budget = (
        db.query(models.Budget).filter_by(id=budget_id, user_id=current_user.id).first()
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    budget.amount = payload.amount
    db.commit()
    db.refresh(budget)
    return to_budget_out(db, budget)


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    budget = (
        db.query(models.Budget).filter_by(id=budget_id, user_id=current_user.id).first()
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()


def current_month() -> str:
    return date.today().strftime("%Y-%m")
