"""Pydantic request/response schemas."""

from datetime import date as Date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ------------------------------------------------------------------ auth ---
class UserRegister(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str


# -------------------------------------------------------------- category ---
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# --------------------------------------------------------------- account ---
class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_type: str = Field(default="checking", max_length=40)
    starting_balance: float = 0.0


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    account_type: str | None = Field(default=None, max_length=40)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    account_type: str
    starting_balance: float
    current_balance: float = 0.0  # computed by the endpoint


# ----------------------------------------------------------- transaction ---
class TransactionCreate(BaseModel):
    account_id: int
    category_id: int | None = None
    amount: float = Field(gt=0)
    type: str = Field(pattern="^(income|expense)$")
    description: str = ""
    date: Date


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    category_id: int | None = None
    amount: float | None = Field(default=None, gt=0)
    type: str | None = Field(default=None, pattern="^(income|expense)$")
    description: str | None = None
    date: Date | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    category_id: int | None
    amount: float
    type: str
    description: str
    date: Date
    category_name: str | None = None
    account_name: str | None = None


# --------------------------------------------------------------- budget ---
class BudgetCreate(BaseModel):
    category_id: int
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: float = Field(gt=0)


class BudgetUpdate(BaseModel):
    amount: float = Field(gt=0)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    month: str
    amount: float
    category_name: str = ""
    spent: float = 0.0  # computed by the endpoint


# --------------------------------------------------------------- summary ---
class CategorySpending(BaseModel):
    category_id: int | None
    category_name: str
    total: float


class MonthlyTotal(BaseModel):
    month: str
    income: float
    expenses: float


class AccountNet(BaseModel):
    account_id: int
    account_name: str
    balance: float


class BudgetProgress(BaseModel):
    category_id: int
    category_name: str
    budgeted: float
    spent: float
    remaining: float


class SummaryOut(BaseModel):
    month: str
    spending_by_category: list[CategorySpending]
    monthly_totals: list[MonthlyTotal]
    net_by_account: list[AccountNet]
    budget_progress: list[BudgetProgress]
    total_income: float
    total_expenses: float
    net_savings: float


# --------------------------------------------------------------- csv import ---
class CsvImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    errors: list[str]
