from datetime import datetime, date, time
from typing import Any, List, Optional, Union, Set, Literal
from enum import Enum
from pydantic import BaseModel, field_validator, model_validator

from abc import ABC, abstractmethod

############################################
# Enumerations are defined here
############################################

class ExpenseType(Enum):
    FIX = "FIX"
    VARIABLE = "VARIABLE"
    EXTRAORDINARY = "EXTRAORDINARY"

############################################
# Classes are defined here
############################################
class EntryCreate(ABC, BaseModel):
    amount: float
    description: str
    endDate: Optional[date] = None
    recurrenceIntervalMonths: Optional[int] = None
    startDate: date
    account: int  # N:1 Relationship (mandatory)
    category: Optional[int] = None  # Categories are optional for entries.

    @field_validator('amount')
    @classmethod
    def positive_amount(cls, value):
        if value is not None and not 0 < value < float('inf'):
            raise ValueError('Amount must be positive and finite')
        return value

    @field_validator('recurrenceIntervalMonths')
    @classmethod
    def positive_interval(cls, value):
        if value is not None and value < 1:
            raise ValueError('Recurrence interval must be at least one month')
        return value

    @model_validator(mode='after')
    def valid_dates(self):
        if self.endDate is not None and self.endDate < self.startDate:
            raise ValueError('End date must not precede start date')
        return self


class IncomeType(str, Enum):
    FIXED = 'FIXED'
    VARIABLE = 'VARIABLE'
    EXTRAORDINARY = 'EXTRAORDINARY'


class IncomeCreate(EntryCreate):
    incomeType: IncomeType = IncomeType.EXTRAORDINARY
    expectedValue: Optional[float] = None
    allowedDeviation: Optional[float] = None
    amount: Optional[float] = None

    @model_validator(mode='after')
    def income_values(self):
        if self.expectedValue is None and self.amount is not None:
            self.expectedValue = self.amount  # Existing income requests supplied only amount.
        if self.allowedDeviation is None and self.amount is not None:
            self.allowedDeviation = 0.0
        if self.allowedDeviation is None:
            raise ValueError('Income deviation is required')
        if self.expectedValue is None or not 0 < self.expectedValue < float('inf'):
            raise ValueError('Income average must be positive and finite')
        if not 0 <= self.allowedDeviation < float('inf'):
            raise ValueError('Income deviation must be nonnegative and finite')
        return self

    @model_validator(mode='after')
    def recurring_income_interval(self):
        if self.incomeType in (IncomeType.FIXED, IncomeType.VARIABLE) and self.recurrenceIntervalMonths is None:
            raise ValueError('Fixed and variable income require a repeat interval in months')
        return self


class ExpenseCreate(EntryCreate):
    expenseType: ExpenseType
    amount: Optional[float] = None
    expectedValue: Optional[float] = None
    allowedDeviation: Optional[float] = None

    @model_validator(mode='after')
    def expense_rules(self):
        if self.expenseType in (ExpenseType.FIX, ExpenseType.VARIABLE) and self.recurrenceIntervalMonths is None:
            raise ValueError('Fixed and variable expenses require Repeat every x months')
        if self.expenseType != ExpenseType.VARIABLE and self.amount is None:
            raise ValueError('Fixed and extraordinary expenses require an amount')
        if self.expenseType == ExpenseType.VARIABLE:
            if self.expectedValue is None or self.allowedDeviation is None:
                raise ValueError('Variable expenses require expected value and allowed deviation')
            if not 0 < self.expectedValue < float('inf') or not 0 <= self.allowedDeviation < float('inf'):
                raise ValueError('Expected value must be positive and deviation must be nonnegative and finite')
        elif self.expectedValue is not None or self.allowedDeviation is not None:
            raise ValueError('Expected value and deviation apply only to variable expenses')
        return self


class TransferCreate(BaseModel):
    fromAccount: int
    toAccount: int
    amount: float
    date: date
    description: str = ''
    recurrenceIntervalMonths: Optional[int] = None
    endDate: Optional[date] = None

    @field_validator('recurrenceIntervalMonths')
    @classmethod
    def positive_interval(cls, value):
        if value is not None and value < 1:
            raise ValueError('Recurrence interval must be at least one month')
        return value

    @field_validator('amount')
    @classmethod
    def positive_amount(cls, value):
        if not 0 < value < float('inf'):
            raise ValueError('Transfer amount must be positive and finite')
        return value

    @model_validator(mode='after')
    def different_accounts(self):
        if self.fromAccount == self.toAccount:
            raise ValueError('Transfer accounts must be different')
        if self.endDate is not None and self.endDate < self.date:
            raise ValueError('End date must not precede transfer date')
        return self


class CategoryCreate(BaseModel):
    name: str
    kind: Literal['income', 'expense']
    entries: Optional[List[int]] = None  # 1:N Relationship


class AccountGroupCreate(BaseModel):
    name: str
    accounts: List[int]  # N:M Relationship


class AccountCreate(BaseModel):
    currency: Literal['EUR', 'BRL', 'USD']
    name: str
    openingBalance: float
    openingBalanceDate: date
    entries: Optional[List[int]] = None  # 1:N Relationship
    groups: Optional[List[int]] = None  # N:M Relationship (optional)


