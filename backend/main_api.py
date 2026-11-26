import time as time_module
import logging
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic_classes import *
from sql_alchemy import *
from sql_alchemy import OccurrenceAmount
from database import get_db, integrity_error_detail
from datetime import date
from cashflow import project, occurrences
from monthly import router as monthly_router
from routers import entry as entry_router
from routers import revenue as income_router
from routers import expense as expense_router
from routers import category as category_router
from routers import accountgroup as accountgroup_router
from routers import account as account_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='Pockindle API',
    description='Auto-generated REST API with full CRUD operations, relationship management, and advanced features',
    version='1.0.0',
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "System", "description": "System health and statistics"},
        {"name": "Entry", "description": "Operations for Entry entities"},
        {"name": "Entry Relationships", "description": "Manage Entry relationships"},
        {"name": "Income", "description": "Operations for Income entities"},
        {"name": "Expense", "description": "Operations for Expense entities"},
        {"name": "Category", "description": "Operations for Category entities"},
        {"name": "Category Relationships", "description": "Manage Category relationships"},
        {"name": "AccountGroup", "description": "Operations for AccountGroup entities"},
        {"name": "AccountGroup Relationships", "description": "Manage AccountGroup relationships"},
        {"name": "Account", "description": "Operations for Account entities"},
        {"name": "Account Relationships", "description": "Manage Account relationships"},
    ]
)

# Enable CORS for all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

############################################
#
#   Middleware
#
############################################

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses."""
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to all responses."""
    start_time = time_module.time()
    response = await call_next(request)
    process_time = time_module.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

############################################
#
#   Exception Handlers
#
############################################

# Global exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    # The client sees a 400; the server log keeps the traceback of the real cause.
    logger.exception("ValueError on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Bad Request",
            "message": str(exc),
            "detail": "Invalid input data provided"
        }
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors."""
    logger.error(f"Database integrity error: {exc}")

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "Conflict",
            "message": "Data conflict occurred",
            "detail": integrity_error_detail(exc)
        }
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general SQLAlchemy errors."""
    logger.exception(f"Database error: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "Database operation failed",
            "detail": "An internal database error occurred"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format.

    `detail` carries the endpoint's actual message — clients (including the
    generated frontend dialog) read it to show the user what went wrong.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "message": exc.detail,
            "detail": exc.detail
        }
    )

############################################
#
#   Routers
#
############################################

app.include_router(monthly_router)
app.include_router(entry_router.router)
app.include_router(income_router.router)
app.include_router(expense_router.router)
app.include_router(category_router.router)
app.include_router(accountgroup_router.router)
app.include_router(account_router.router)

############################################
#
#   Global API endpoints
#
############################################

@app.get("/", tags=["System"])
def root():
    """Root endpoint - API information"""
    return {
        "name": app.title,
        "version": app.version,
        "status": "running"
    }


@app.get("/health", tags=["System"])
def health_check(database: Session = Depends(get_db)):
    """Health check endpoint for monitoring.

    Actually touches the database — a health check that hardcodes
    "connected" is worse than none.
    """
    from datetime import datetime
    from sqlalchemy import text as _sql_text
    try:
        database.execute(_sql_text("SELECT 1"))
        db_status = "connected"
    except Exception:
        raise HTTPException(status_code=503, detail={
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "database": "error",
        })
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
    }


@app.get('/transfer/', tags=['Transfer'])
def list_transfers(database: Session = Depends(get_db)):
    return database.query(Transfer).order_by(Transfer.date.desc(), Transfer.id.desc()).all()


@app.post('/transfer/', tags=['Transfer'])
def create_transfer(transfer: TransferCreate, database: Session = Depends(get_db)):
    source = database.get(Account, transfer.fromAccount)
    destination = database.get(Account, transfer.toAccount)
    if source is None or destination is None:
        raise HTTPException(status_code=404, detail='Both transfer accounts must exist')
    if source.currency != destination.currency:
        raise HTTPException(status_code=422, detail='Transfer accounts must share a currency')
    if transfer.date < source.openingBalanceDate or transfer.date < destination.openingBalanceDate:
        raise HTTPException(status_code=422, detail='Transfer date must not precede either opening balance date')
    record = Transfer(fromAccount_id=source.id, toAccount_id=destination.id,
                      amount=transfer.amount, date=transfer.date, description=transfer.description,
                      recurrenceIntervalMonths=transfer.recurrenceIntervalMonths, endDate=transfer.endDate)
    database.add(record)
    database.commit()
    database.refresh(record)
    return record


@app.get('/transfer/{transfer_id}/', tags=['Transfer'])
def get_transfer(transfer_id: int, database: Session = Depends(get_db)):
    record = database.get(Transfer, transfer_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Transfer not found')
    return {'transfer': record}


@app.delete('/transfer/{transfer_id}/', tags=['Transfer'])
def delete_transfer(transfer_id: int, database: Session = Depends(get_db)):
    record = database.get(Transfer, transfer_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Transfer not found')
    result = {'id': record.id}
    database.delete(record)
    database.commit()
    return result


@app.get('/overview/overages/', tags=['System'])
def expense_overages(database: Session = Depends(get_db)):
    """Historical expense overages and income shortfalls with recorded actuals."""
    from decimal import Decimal
    today = date.today()
    overrides = {(row.entry_id, row.date): row.amount for row in database.query(OccurrenceAmount).all()}
    result = []
    for entry in database.query(Entry).all():
        if entry.type_spec not in ('expense', 'income') or entry.expectedValue is None or entry.allowedDeviation is None:
            continue
        first = max(entry.startDate, entry.account.openingBalanceDate)
        last = min(today, entry.endDate or today)
        if first > last:
            continue
        deviation = Decimal(str(entry.allowedDeviation))
        expected = Decimal(str(entry.expectedValue))
        threshold = expected + deviation if entry.type_spec == 'expense' else expected - deviation
        for day in occurrences(entry, first, last):
            # Only amounts explicitly entered for a month establish an off-plan occurrence.
            actual = overrides.get((entry.id, day))
            if actual is None and day == entry.startDate and entry.amount is not None and entry.amount != entry.expectedValue:
                actual = entry.amount
            if actual is not None and (Decimal(str(actual)) > threshold if entry.type_spec == 'expense' else Decimal(str(actual)) < threshold):
                result.append({'id': entry.id, 'kind': entry.type_spec, 'date': day,
                               'description': entry.description, 'account_id': entry.account_id,
                               'category_id': entry.category_id, 'amount': actual,
                               'expectedValue': entry.expectedValue, 'allowedDeviation': entry.allowedDeviation,
                               'limit': float(threshold)})
    return sorted(result, key=lambda row: (row['date'], row['id']), reverse=True)


@app.get('/dashboard/', tags=['System'])
def dashboard(months: int = 6, low_balance_threshold: float = 0, reporting_currency: str = 'EUR',
              brl_rate: float | None = None, usd_rate: float | None = None,
              eur_rate: float | None = None, database: Session = Depends(get_db)):
    if low_balance_threshold < 0:
        raise HTTPException(status_code=422, detail='Low balance threshold must not be negative')
    if not 1 <= months <= 60:
        raise HTTPException(status_code=422, detail='Months must be between 1 and 60')
    accounts = database.query(Account).all()
    by_currency = {}
    for currency in sorted({a.currency for a in accounts}):
        selected = [a for a in accounts if a.currency == currency]
        projection = project(database, selected, months)
        by_currency[currency] = {
            'months': projection,
            'currentMonthSpending': projection[0]['spending'],
            'futureMonthSpending': sum(m['spending'] for m in projection[1:]),
            'averageMonthlySpending': round(sum(m['spending'] for m in projection) / months, 2),
        }
    from cashflow import month_end
    from decimal import Decimal
    first = date.today().replace(day=1)
    last = month_end(first)
    categories = {category.id: category.name for category in database.query(Category).all()}
    entries = database.query(Entry).all()
    overrides = {(item.entry_id, item.date): item.amount for item in database.query(OccurrenceAmount).all()}
    for currency, summary in by_currency.items():
        selected = [a for a in accounts if a.currency == currency]
        summary['accounts'] = [
            {'id': a.id, 'name': a.name, 'months': project(database, [a], months)}
            for a in selected
        ]
        summary['groups'] = [
            {'id': group.id, 'name': group.name, 'months': project(database, members, months)}
            for group in database.query(AccountGroup).all()
            if (members := [a for a in group.accounts]) and all(a.currency == currency for a in members)
        ]
        chart = {'income': {}, 'expense': {}}
        selected_ids = {a.id for a in selected}
        for entry in entries:
            if entry.account_id not in selected_ids or entry.type_spec not in chart:
                continue
            account = next(a for a in selected if a.id == entry.account_id)
            count = sum(1 for day in occurrences(entry, max(first, account.openingBalanceDate), last))
            if count:
                name = categories.get(entry.category_id, 'Uncategorized')
                amounts = chart[entry.type_spec]
                for day in occurrences(entry, max(first, account.openingBalanceDate), last):
                    expected = getattr(entry, 'expectedValue', None)
                    value = entry.amount if day == entry.startDate else (expected if expected is not None else entry.amount)
                    amounts[name] = amounts.get(name, Decimal('0')) + Decimal(str(overrides.get((entry.id, day), value)))
        summary['categories'] = {
            kind: [{'name': name, 'amount': float(amount)} for name, amount in sorted(values.items())]
            for kind, values in chart.items()
        }
    from cashflow import add_months, occurrences_at
    from monthly import monthly_rows
    from datetime import timedelta
    today = date.today()
    previous = add_months(today, -1)
    horizon = today + timedelta(days=14)
    all_transfers = database.query(Transfer).all()

    def balance_on(account, day):
        """Opening balance plus scheduled activity through the given day."""
        if day < account.openingBalanceDate:
            return 0.0
        balance = Decimal(str(account.openingBalance))
        for entry in entries:
            if entry.account_id != account.id:
                continue
            for occurrence in occurrences(entry, account.openingBalanceDate, day):
                expected = getattr(entry, 'expectedValue', None)
                amount = overrides.get((entry.id, occurrence))
                if amount is None:
                    amount = entry.amount if occurrence == entry.startDate and entry.amount is not None else expected if expected is not None else entry.amount
                balance += Decimal(str(amount or 0)) * (1 if entry.type_spec == 'income' else -1)
        for transfer in all_transfers:
            if account.id not in (transfer.fromAccount_id, transfer.toAccount_id):
                continue
            for occurrence in occurrences_at(transfer.date, transfer.recurrenceIntervalMonths, transfer.endDate, account.openingBalanceDate, day):
                balance += Decimal(str(transfer.amount)) * (1 if account.id == transfer.toAccount_id else -1)
        return float(balance)

    current_rows = monthly_rows(database, 'entry', today.strftime('%Y-%m'))
    prior_rows = [monthly_rows(database, 'entry', add_months(today, -index).strftime('%Y-%m')) for index in range(1, 7)]
    for currency, summary in by_currency.items():
        selected = [a for a in accounts if a.currency == currency]
        ids = {a.id for a in selected}
        rows = [row for row in current_rows if row['account_id'] in ids and row['date'] <= today]
        scheduled = [row for row in current_rows if row['account_id'] in ids]
        summary['todayBalance'] = sum(balance_on(a, today) for a in selected)
        summary['changeSinceLastMonth'] = summary['todayBalance'] - sum(balance_on(a, previous) for a in selected)
        summary['balanceTrendDates'] = [add_months(today, -index).isoformat() for index in range(5, -1, -1)]
        summary['balanceTrend'] = [sum(balance_on(a, add_months(today, -index)) for a in selected) for index in range(5, -1, -1)]
        for item in summary['accounts']:
            account = next(a for a in selected if a.id == item['id'])
            item['todayBalance'] = balance_on(account, today)
            item['balanceTrend'] = [balance_on(account, add_months(today, -index)) for index in range(5, -1, -1)]
        def actual(row):
            return row['amount'] if not row['needsActual'] else None
        income_expected = sum(row['expectedValue'] or 0 for row in rows if row['kind'] == 'income')
        expense_planned = sum(row['expectedValue'] if row['expectedValue'] is not None else row['amount'] or 0 for row in rows if row['kind'] == 'expense')
        recorded = {(entry_id, day) for entry_id, day in overrides}
        def occurred(row):
            entry = next(e for e in entries if e.id == row['id'])
            return (row['id'], row['date']) in recorded or (row['date'] == entry.startDate and entry.amount is not None)
        received = sum(actual(row) or 0 for row in rows if row['kind'] == 'income' and occurred(row))
        spent = sum(actual(row) or 0 for row in rows if row['kind'] == 'expense' and occurred(row))
        fixed = sum(row['expectedValue'] if row['expectedValue'] is not None else row['amount'] or 0 for row in scheduled if row['kind'] == 'expense' and row['type'] in ('FIX', 'FIXED'))
        expected_month_income = sum(row['expectedValue'] or 0 for row in scheduled if row['kind'] == 'income')
        month_income = sum(row['amount'] if row['amount'] is not None else row['expectedValue'] or 0
                           for row in scheduled if row['kind'] == 'income')
        month_expenses = sum(row['amount'] if row['amount'] is not None else row['expectedValue'] or 0
                             for row in scheduled if row['kind'] == 'expense')
        summary['monthToDate'] = {'incomeReceived': received, 'incomeExpected': income_expected,
                                  'expensesSpent': spent, 'expensesPlanned': expense_planned,
                                  'leftToSpend': round(month_income - month_expenses, 2),
                                  'monthlyIncome': round(month_income, 2),
                                  'fixedCosts': fixed, 'monthlyIncomeExpected': expected_month_income}
        summary['missingAmounts'] = [{'id': row['id'], 'kind': row['kind'], 'description': row['description'], 'date': row['date']}
                                     for row in rows if row['needsActual'] and row['type'] == 'VARIABLE']
        timeline = []
        for entry in entries:
            if entry.account_id not in ids:
                continue
            account = next(a for a in selected if a.id == entry.account_id)
            for day in occurrences(entry, max(today, account.openingBalanceDate), horizon):
                expected = getattr(entry, 'expectedValue', None)
                amount = overrides.get((entry.id, day), entry.amount if day == entry.startDate and entry.amount is not None else expected if expected is not None else entry.amount)
                timeline.append({'date': day.isoformat(), 'description': entry.description, 'kind': entry.type_spec,
                                 'amount': amount or 0, 'account': account.name, 'account_id': account.id,
                                 'canCover': entry.type_spec != 'expense' or balance_on(account, day) >= 0})
        summary['timeline'] = sorted(timeline, key=lambda row: (row['date'], row['description']))
        alerts = []
        for kind, items in (('account', summary['accounts']), ('group', summary['groups'])):
            for item in items:
                first_low = next((row for row in item['months'] if row['endBalance'] < low_balance_threshold), None)
                if first_low:
                    alerts.append({'name': item['name'], 'month': first_low['month'], 'balance': first_low['endBalance'],
                                   'threshold': low_balance_threshold, 'kind': kind, 'id': item['id']})
        summary['lowBalances'] = sorted(alerts, key=lambda row: (row['month'], row['balance']))
        summary['lowBalance'] = summary['lowBalances'][0] if alerts else None
        if summary['lowBalance'] and summary['lowBalance']['kind'] == 'account':
            candidate = next((a for a in summary['accounts'] if a['id'] != summary['lowBalance']['id']
                              and next((m['endBalance'] for m in a['months'] if m['month'] == summary['lowBalance']['month']), 0) > -summary['lowBalance']['balance']), None)
            summary['lowBalance']['transferFrom'] = candidate['name'] if candidate else None
        off_plan = []
        for row in rows:
            if row['amount'] is None or not occurred(row):
                continue
            limit = row['expectedMaximum'] if row['kind'] == 'expense' else row['expectedMinimum']
            if limit is not None:
                difference = row['amount'] - limit if row['kind'] == 'expense' else limit - row['amount']
                if difference > 0:
                    off_plan.append({'description': row['description'], 'kind': row['kind'], 'difference': difference, 'date': row['date']})
        summary['offPlan'] = {'count': len(off_plan), 'worst': max(off_plan, key=lambda row: row['difference']) if off_plan else None}
        summary['spendingTypes'] = {kind: sum(row['expectedValue'] if row['expectedValue'] is not None else row['amount'] or 0 for row in scheduled if row['kind'] == 'expense' and row['type'] in types)
                                    for kind, types in [('fixed', ('FIX', 'FIXED')), ('variable', ('VARIABLE',)), ('extraordinary', ('EXTRAORDINARY',))]}
        category_names = {c.id: c.name for c in database.query(Category).all()}
        current_categories = {}
        for row in scheduled:
            if row['kind'] == 'expense':
                name = category_names.get(row['category_id'], 'Uncategorized')
                current_categories[name] = current_categories.get(name, 0) + (row['amount'] if row['amount'] is not None else row['expectedValue'] or 0)
        history = []
        for past in prior_rows:
            totals = {}
            for row in past:
                if row['account_id'] in ids and row['kind'] == 'expense':
                    name = category_names.get(row['category_id'], 'Uncategorized')
                    totals[name] = totals.get(name, 0) + (row['amount'] if row['amount'] is not None else row['expectedValue'] or 0)
            history.append(totals)
        summary['categoryComparison'] = [{'name': name, 'current': value,
                                           'average': sum(past.get(name, 0) for past in history) / len(history)}
                                          for name, value in sorted(current_categories.items())]
        summary['recurringCosts'] = sorted([{'description': e.description, 'yearly': (e.expectedValue or e.amount or 0) * 12 / e.recurrenceIntervalMonths,
                                              'monthly': (e.expectedValue or e.amount or 0) / e.recurrenceIntervalMonths}
                                             for e in entries if e.account_id in ids and e.type_spec == 'expense' and e.recurrenceIntervalMonths],
                                            key=lambda item: -item['yearly'])
        summary['endingSoon'] = [{'description': e.description, 'endDate': e.endDate.isoformat(),
                                  'monthlyChange': (e.expectedValue if e.expectedValue is not None else e.amount or 0) / (e.recurrenceIntervalMonths or 1) * (1 if e.type_spec == 'expense' else -1)}
                                 for e in entries if e.account_id in ids and e.recurrenceIntervalMonths and e.endDate
                                 and today <= e.endDate <= add_months(today, 3)
                                 and any(True for _ in occurrences(e, today, e.endDate))]
        summary['savingsRates'] = [{'month': row['month'], 'rate': (row['income'] - row['spending']) / row['income'] * 100 if row['income'] else None} for row in summary['months']]
        future = add_months(today, 12)
        upcoming = []
        for e in entries:
            if e.account_id not in ids or e.type_spec != 'expense' or e.recurrenceIntervalMonths not in (None, 12):
                continue
            for day in occurrences(e, today, future):
                amount = overrides.get((e.id, day))
                if amount is None:
                    amount = e.amount if day == e.startDate and e.amount is not None else e.expectedValue if e.expectedValue is not None else e.amount or 0
                upcoming.append({'description': e.description, 'date': day.isoformat(), 'amount': amount,
                                 'monthlySetAside': amount / max(1, (day.year - today.year) * 12 + day.month - today.month + 1)})
        # Compare upcoming one-offs and yearly bills with ordinary monthly spending.
        ordinary = sorted(row['amount'] if row['amount'] is not None else row['expectedValue'] or 0
                          for row in scheduled if row['kind'] == 'expense'
                          and row['type'] in ('FIX', 'FIXED', 'VARIABLE'))
        typical = ordinary[len(ordinary) // 2] if ordinary else 0
        summary['bigUpcoming'] = sorted((row for row in upcoming if row['amount'] > typical and row['amount'] > 0),
                                        key=lambda row: -row['amount'])[:5]
        # Average the last six months of scheduled fixed and variable costs.
        # For variable expenses use the expected amount rather than an optional
        # actual, so a missing monthly update does not reduce emergency cover.
        cost_history = [sum(row['expectedValue'] if row['expectedValue'] is not None else row['amount'] or 0
                            for row in past if row['account_id'] in ids and row['kind'] == 'expense'
                            and row['type'] in ('FIX', 'FIXED', 'VARIABLE')) for past in prior_rows]
        # Use scheduled costs for the current and following months when history
        # is not yet available (a newly created account has no past six months).
        future_costs = [sum(row['expectedValue'] if row['expectedValue'] is not None else row['amount'] or 0
                            for row in monthly_rows(database, 'expense', month['month'])
                            if row['account_id'] in ids and row['type'] in ('FIX', 'FIXED', 'VARIABLE'))
                        for month in summary['months']]
        active_costs = cost_history if any(cost > 0 for cost in cost_history) else future_costs
        average_costs = sum(active_costs) / len(active_costs) if active_costs else 0
        # With no fixed or variable costs, show a numeric zero instead of a missing value.
        summary['emergencyCover'] = round(summary['todayBalance'] / average_costs, 1) if average_costs else 0.0
    if reporting_currency not in ('EUR', 'BRL', 'USD'):
        raise HTTPException(status_code=422, detail='Reporting currency must be EUR, BRL or USD')
    provided = {'EUR': eur_rate, 'BRL': brl_rate, 'USD': usd_rate}
    rates = {currency: 1.0 if currency == reporting_currency else provided[currency]
             for currency in by_currency}
    missing_rates = [currency for currency, rate in rates.items() if rate is None]
    if any(rate is not None and not 0 < rate < float('inf') for rate in rates.values()):
        raise HTTPException(status_code=422, detail='Conversion rates must be positive and finite')
    net_worth = None if missing_rates else {
        'currency': reporting_currency,
        'todayBalance': round(sum(summary['todayBalance'] * rates[currency] for currency, summary in by_currency.items()), 2),
        'changeSinceLastMonth': round(sum(summary['changeSinceLastMonth'] * rates[currency] for currency, summary in by_currency.items()), 2),
        'balanceTrendDates': [add_months(today, -index).isoformat() for index in range(5, -1, -1)],
        'balanceTrend': [round(sum(summary['balanceTrend'][index] * rates[currency]
                                   for currency, summary in by_currency.items()), 2) for index in range(6)],
    }
    return {'asOf': today.isoformat(), 'currencies': by_currency, 'netWorth': net_worth,
            'missingConversionRates': missing_rates}


@app.get("/statistics", tags=["System"])
def get_statistics(database: Session = Depends(get_db)):
    """Get database statistics for all entities"""
    stats = {}
    stats["entry_count"] = database.query(Entry).count()
    stats["income_count"] = database.query(Income).count()
    stats["expense_count"] = database.query(Expense).count()
    stats["category_count"] = database.query(Category).count()
    stats["accountgroup_count"] = database.query(AccountGroup).count()
    stats["account_count"] = database.query(Account).count()
    stats["total_entities"] = sum(stats.values())
    return stats


############################################
# Maintaining the server
############################################
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
