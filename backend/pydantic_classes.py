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
        if not 0 < value < float('inf'):
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


class RevenueCreate(EntryCreate):
    pass


class ExpenseCreate(EntryCreate):
    expenseType: ExpenseType


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
    kind: Literal['revenue', 'expense']
    entries: Optional[List[int]] = None  # 1:N Relationship


class AccountGroupCreate(BaseModel):
    name: str
    accounts: List[int]  # N:M Relationship


class AccountCreate(BaseModel):
    currency: str
    name: str
    openingBalance: float
    openingBalanceDate: date
    entries: Optional[List[int]] = None  # 1:N Relationship
    groups: Optional[List[int]] = None  # N:M Relationship (optional)


