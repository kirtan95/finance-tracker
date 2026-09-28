"""Aggregated dashboard data: spending by category, monthly totals,
net worth by account, and budget progress."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db
from ..utils import month_expr_for

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=schemas.SummaryOut)
def get_summary(
    month: str | None = Query(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"
    ),
    history_months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    target = month or date.today().strftime("%Y-%m")
    uid = current_user.id
    month_expr = month_expr_for(db, models.Transaction.date)

    # --- spending by category for the target month (expenses only) ------------
    rows = (
        db.query(
            models.Transaction.category_id,
            func.coalesce(func.max(models.Category.name), "Uncategorized").label("name"),
            func.coalesce(func.sum(models.Transaction.amount), 0.0).label("total"),
        )
        .outerjoin(
            models.Category, models.Transaction.category_id == models.Category.id
        )
        .filter(
            models.Transaction.user_id == uid,
            models.Transaction.type == "expense",
            month_expr == target,
        )
        .group_by(models.Transaction.category_id)
        .order_by(func.sum(models.Transaction.amount).desc())
        .all()
    )
    spending = [
        schemas.CategorySpending(
            category_id=r[0], category_name=r[1], total=round(float(r[2] or 0), 2)
        )
        for r in rows
    ]

    # --- monthly income vs expenses over the trailing N months ----------------
    # Compute the window in Python to avoid DB-specific date arithmetic.
    year, mon = int(target[:4]), int(target[5:7])
    months: list[str] = []
    for _ in range(history_months):
        months.append(f"{year:04d}-{mon:02d}")
        mon -= 1
        if mon == 0:
            mon, year = 12, year - 1
    earliest = months[-1]

    totals_rows = (
        db.query(
            month_expr.label("month"),
            func.coalesce(
                func.sum(
                    case((models.Transaction.type == "income", models.Transaction.amount), else_=0.0)
                ),
                0.0,
            ).label("income"),
            func.coalesce(
                func.sum(
                    case((models.Transaction.type == "expense", models.Transaction.amount), else_=0.0)
                ),
                0.0,
            ).label("expenses"),
        )
        .filter(
            models.Transaction.user_id == uid,
            month_expr >= earliest,
            month_expr <= target,
        )
        .group_by(month_expr)
        .all()
    )
    by_month = {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in totals_rows}
    monthly = [
        schemas.MonthlyTotal(
            month=m,
            income=round(by_month.get(m, (0.0, 0.0))[0], 2),
            expenses=round(by_month.get(m, (0.0, 0.0))[1], 2),
        )
        for m in reversed(months)  # oldest -> newest for charting
    ]

    # --- net worth by account --------------------------------------------------
    accounts = db.query(models.Account).filter_by(user_id=uid).all()
    net_by_account: list[schemas.AccountNet] = []
    for a in accounts:
        delta = (
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
            .filter(models.Transaction.account_id == a.id)
            .scalar()
        )
        net_by_account.append(
            schemas.AccountNet(
                account_id=a.id,
                account_name=a.name,
                balance=round(float(a.starting_balance + (delta or 0.0)), 2),
            )
        )

    # --- budget progress for the target month ----------------------------------
    budgets = db.query(models.Budget).filter_by(user_id=uid, month=target).all()
    progress: list[schemas.BudgetProgress] = []
    for b in budgets:
        spent = (
            db.query(func.coalesce(func.sum(models.Transaction.amount), 0.0))
            .filter(
                models.Transaction.user_id == uid,
                models.Transaction.category_id == b.category_id,
                models.Transaction.type == "expense",
                month_expr == target,
            )
            .scalar()
        )
        spent_f = float(spent or 0.0)
        progress.append(
            schemas.BudgetProgress(
                category_id=b.category_id,
                category_name=b.category.name if b.category else "",
                budgeted=round(float(b.amount), 2),
                spent=round(spent_f, 2),
                remaining=round(float(b.amount) - spent_f, 2),
            )
        )

    target_income = next(
        (m.income for m in monthly if m.month == target), 0.0
    )
    target_expenses = next(
        (m.expenses for m in monthly if m.month == target), 0.0
    )

    return schemas.SummaryOut(
        month=target,
        spending_by_category=spending,
        monthly_totals=monthly,
        net_by_account=net_by_account,
        budget_progress=progress,
        total_income=round(target_income, 2),
        total_expenses=round(target_expenses, 2),
        net_savings=round(target_income - target_expenses, 2),
    )
