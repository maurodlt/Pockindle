"""Monthly entry occurrence representation and per-date amount edits."""
from datetime import date
from math import isfinite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from database import get_db
from cashflow import occurrences
from sql_alchemy import Entry, Expense, Income, OccurrenceAmount

router = APIRouter()


def monthly_rows(database: Session, kind: str, month: str):
    try:
        first = date.fromisoformat(month + '-01')
        if first.strftime('%Y-%m') != month:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=422, detail='Month must be YYYY-MM')
    from cashflow import month_end
    last = month_end(first)
    model = {'entry': Entry, 'expense': Expense, 'income': Income}[kind]
    records = database.query(model).all()
    overrides = {(item.entry_id, item.date): item.amount for item in database.query(OccurrenceAmount).all()}
    result = []
    for record in records:
        for day in occurrences(record, first, last):
            overridden = (record.id, day) in overrides
            variable = isinstance(record, Expense) and record.expenseType.value == 'VARIABLE'
            expected = record.expectedValue if variable else (record.expectedValue if isinstance(record, Income) and record.expectedValue is not None else record.amount)
            amount = overrides.get((record.id, day), record.amount if day == record.startDate and record.amount is not None and not variable else expected)
            needs_actual = variable and not overridden
            if needs_actual:
                amount = None
            result.append({
                'id': record.id, 'date': day, 'description': record.description,
                'account_id': record.account_id, 'category_id': record.category_id,
                'kind': record.type_spec,
                'type': record.expenseType.value if isinstance(record, Expense) else record.incomeType if isinstance(record, Income) else 'EXTRAORDINARY',
                'amount': amount, 'expectedValue': expected,
                'allowedDeviation': record.allowedDeviation if isinstance(record, (Expense, Income)) else None,
                'expectedMinimum': expected - record.allowedDeviation if isinstance(record, (Expense, Income)) and record.allowedDeviation is not None else None,
                'expectedMaximum': expected + record.allowedDeviation if isinstance(record, (Expense, Income)) and record.allowedDeviation is not None else None,
                'needsActual': needs_actual,
                'overridden': overridden,
            })
    order = {'FIX': 0, 'FIXED': 0, 'VARIABLE': 1, 'EXTRAORDINARY': 2}
    return sorted(result, key=lambda row: (order.get(row['type'], 2), row['date'], row['id']))


class AmountEdit(BaseModel):
    amount: float

    @field_validator('amount')
    @classmethod
    def positive(cls, value):
        if not isfinite(value) or value <= 0:
            raise ValueError('Amount must be positive and finite')
        return value


@router.get('/{kind}/monthly/', tags=['Monthly entries'])
def month_entries(kind: str, month: str, database: Session = Depends(get_db)):
    if kind not in ('entry', 'income', 'expense'):
        raise HTTPException(status_code=404, detail='Unknown entry kind')
    return monthly_rows(database, kind, month)


@router.put('/{kind}/{entry_id}/occurrences/{day}/', tags=['Monthly entries'])
def edit_occurrence(kind: str, entry_id: int, day: date, edit: AmountEdit, database: Session = Depends(get_db)):
    if kind not in ('income', 'expense'):
        raise HTTPException(status_code=404, detail='Unknown entry kind')
    record = database.get(Income if kind == 'income' else Expense, entry_id)
    if record is None or not any(True for _ in occurrences(record, day, day)):
        raise HTTPException(status_code=404, detail='Scheduled occurrence not found')
    if day < record.account.openingBalanceDate:
        raise HTTPException(status_code=422, detail='Occurrence precedes the account opening balance date')
    override = database.get(OccurrenceAmount, (entry_id, day))
    if override is None:
        override = OccurrenceAmount(entry_id=entry_id, date=day, amount=edit.amount)
        database.add(override)
    else:
        override.amount = edit.amount
    database.commit()
    return next(row for row in monthly_rows(database, kind, day.strftime('%Y-%m')) if row['id'] == entry_id and row['date'] == day)
