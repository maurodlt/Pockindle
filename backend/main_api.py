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
    """Historical actual expense occurrences above their average plus deviation."""
    from decimal import Decimal
    today = date.today()
    overrides = {(row.entry_id, row.date): row.amount for row in database.query(OccurrenceAmount).all()}
    result = []
    for expense in database.query(Expense).all():
        if expense.expectedValue is None or expense.allowedDeviation is None:
            continue
        first = max(expense.startDate, expense.account.openingBalanceDate)
        last = min(today, expense.endDate or today)
        if first > last:
            continue
        threshold = Decimal(str(expense.expectedValue)) + Decimal(str(expense.allowedDeviation))
        for day in occurrences(expense, first, last):
            # The first month's entered amount and explicit monthly edits are
            # actuals; later unedited variable months are only estimates.
            actual = overrides.get((expense.id, day))
            if actual is None and day == expense.startDate and expense.amount != expense.expectedValue:
                actual = expense.amount
            if actual is None and expense.expenseType.value == 'FIX':
                actual = expense.amount
            if actual is not None and Decimal(str(actual)) > threshold:
                result.append({'id': expense.id, 'date': day, 'description': expense.description,
                               'account_id': expense.account_id, 'category_id': expense.category_id,
                               'amount': actual, 'expectedValue': expense.expectedValue,
                               'allowedDeviation': expense.allowedDeviation, 'limit': float(threshold)})
    return sorted(result, key=lambda row: (row['date'], row['id']), reverse=True)


@app.get('/dashboard/', tags=['System'])
def dashboard(months: int = 6, database: Session = Depends(get_db)):
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
    return {'asOf': date.today().isoformat(), 'currencies': by_currency}


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
