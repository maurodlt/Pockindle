"""Projected monthly cash movement, calculated from dated entry occurrences."""

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sql_alchemy import Account, Entry, Expense, OccurrenceAmount, Transfer


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def month_end(day: date) -> date:
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def occurrences(entry: Entry, first: date, last: date):
    """A missing interval is a one-off; recurring dates retain the original day."""
    if entry.startDate > last:
        return
    interval = entry.recurrenceIntervalMonths
    if interval is None:
        if first <= entry.startDate <= last and (
            entry.endDate is None or entry.startDate <= entry.endDate
        ):
            yield entry.startDate
        return
    # Request validation ensures interval is positive.
    index = max(
        0,
        ((first.year - entry.startDate.year) * 12 + first.month - entry.startDate.month)
        // interval
        - 1,
    )
    while True:
        occurrence = add_months(entry.startDate, index * interval)
        if occurrence > last or (
            entry.endDate is not None and occurrence > entry.endDate
        ):
            break
        if occurrence >= first:
            yield occurrence
        index += 1


def occurrences_at(start: date, interval: int | None, end: date | None, first: date, last: date):
    """Project a transfer on its date and, optionally, every interval months."""
    if start > last:
        return
    if interval is None:
        if first <= start <= last and (end is None or start <= end):
            yield start
        return
    index = max(0, ((first.year - start.year) * 12 + first.month - start.month) // interval - 1)
    while True:
        day = add_months(start, index * interval)
        if day > last or (end is not None and day > end):
            break
        if day >= first:
            yield day
        index += 1


def project(
    database: Session,
    accounts: list[Account],
    months: int = 12,
    today: date | None = None,
) -> list[dict]:
    today = today or date.today()
    first_month = today.replace(day=1)
    last = month_end(add_months(first_month, months - 1))
    account_ids = [account.id for account in accounts]
    entries = (
        database.query(Entry).filter(Entry.account_id.in_(account_ids)).all()
        if account_ids
        else []
    )
    overrides = {(item.entry_id, item.date): item.amount for item in database.query(OccurrenceAmount).filter(OccurrenceAmount.entry_id.in_([entry.id for entry in entries])).all()} if entries else {}
    buckets = [dict(income=Decimal("0"), spending=Decimal("0")) for _ in range(months)]
    balance = sum((Decimal(str(a.openingBalance)) for a in accounts if a.openingBalanceDate < first_month), Decimal('0'))
    for entry in entries:
        account = next(a for a in accounts if a.id == entry.account_id)
        for day in occurrences(entry, account.openingBalanceDate, last):
            index = (day.year - today.year) * 12 + day.month - today.month
            key = "spending" if entry.type_spec == "expense" else "income"
            expected = (entry.expectedValue if entry.expectedValue is not None and
                        (day != entry.startDate or entry.amount is None) else entry.amount)
            amount = Decimal(str(overrides.get((entry.id, day), expected)))
            if day < first_month:
                balance += amount * (-1 if key == 'spending' else 1)
            elif 0 <= index < months:
                buckets[index][key] += amount
    transfers = (
        database.query(Transfer).filter(
            (Transfer.fromAccount_id.in_(account_ids)) | (Transfer.toAccount_id.in_(account_ids))
        ).all() if account_ids else []
    )
    for transfer in transfers:
        # Transfers use the same monthly recurrence semantics as entries.
        for day in occurrences_at(transfer.date, transfer.recurrenceIntervalMonths,
                                  transfer.endDate, min((a.openingBalanceDate for a in accounts), default=first_month), last):
            index = (day.year - today.year) * 12 + day.month - today.month
            for account_id, sign, key in ((transfer.fromAccount_id, -1, 'spending'), (transfer.toAccount_id, 1, 'income')):
                if account_id in account_ids:
                    account = next(a for a in accounts if a.id == account_id)
                    if day >= account.openingBalanceDate:
                        amount = Decimal(str(transfer.amount))
                        if day < first_month:
                            balance += sign * amount
                        else:
                            buckets[index][key] += amount
    result = []
    for index, bucket in enumerate(buckets):
        start = add_months(first_month, index)
        # Accounts with a future balance date contribute when that date arrives.
        opening = sum(
            (
                Decimal(str(a.openingBalance))
                for a in accounts
                if (index == 0 and start <= a.openingBalanceDate <= month_end(start))
                or (
                    index > 0
                    and a.openingBalanceDate.year == start.year
                    and a.openingBalanceDate.month == start.month
                )
            ),
            Decimal("0"),
        )
        balance += opening
        balance += bucket["income"] - bucket["spending"]
        result.append(
            {
                "month": start.strftime("%Y-%m"),
                "income": float(bucket["income"]),
                "spending": float(bucket["spending"]),
                "endBalance": float(balance),
            }
        )
    return result
