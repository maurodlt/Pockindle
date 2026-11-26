"""Projected monthly cash movement, calculated from dated entry occurrences."""

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sql_alchemy import Account, Entry


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
    buckets = [dict(revenue=Decimal("0"), spending=Decimal("0")) for _ in range(months)]
    for entry in entries:
        account = next(a for a in accounts if a.id == entry.account_id)
        for day in occurrences(entry, account.openingBalanceDate, last):
            if day < first_month:
                continue  # Previous activity is already represented by the opening balance.
            index = (day.year - today.year) * 12 + day.month - today.month
            if 0 <= index < months:
                key = "spending" if entry.type_spec == "expense" else "revenue"
                buckets[index][key] += Decimal(str(entry.amount))
    balance = Decimal("0")
    result = []
    for index, bucket in enumerate(buckets):
        start = add_months(first_month, index)
        # Accounts with a future balance date contribute when that date arrives.
        opening = sum(
            (
                Decimal(str(a.openingBalance))
                for a in accounts
                if (index == 0 and a.openingBalanceDate <= month_end(start))
                or (
                    index > 0
                    and a.openingBalanceDate.year == start.year
                    and a.openingBalanceDate.month == start.month
                )
            ),
            Decimal("0"),
        )
        balance += opening
        balance += bucket["revenue"] - bucket["spending"]
        result.append(
            {
                "month": start.strftime("%Y-%m"),
                "revenue": float(bucket["revenue"]),
                "spending": float(bucket["spending"]),
                "endBalance": float(balance),
            }
        )
    return result
