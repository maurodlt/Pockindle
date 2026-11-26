import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from pydantic_classes import *
from sql_alchemy import *
from sql_alchemy import OccurrenceAmount
from database import get_db, integrity_error_detail
from bal_stdlib import *

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/expense/", response_model=None, tags=["Expense"])
def get_all_expense(detailed: bool = False, database: Session = Depends(get_db)) -> list:
    # Use detailed=true to get entities with eagerly loaded relationships (for tables with lookup columns)
    if detailed:
        # Eagerly load all relationships to avoid N+1 queries
        query = database.query(Expense)
        query = query.options(joinedload(Expense.account))
        query = query.options(joinedload(Expense.category))
        expense_list = query.all()

        # Serialize with relationships included
        result = []
        for db_expense in expense_list:
            item_dict = db_expense.__dict__.copy()
            item_dict.pop('_sa_instance_state', None)

            # Add many-to-one relationships (foreign keys for lookup columns)
            if db_expense.account:
                related_obj = db_expense.account
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['account'] = related_dict
            else:
                item_dict['account'] = None
            if db_expense.category:
                related_obj = db_expense.category
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['category'] = related_dict
            else:
                item_dict['category'] = None


            result.append(item_dict)
        return result
    else:
        # Default: return flat entities (faster for charts/widgets without lookup columns)
        return database.query(Expense).all()


@router.get("/expense/count/", response_model=None, tags=["Expense"])
def get_count_expense(database: Session = Depends(get_db)) -> dict:
    """Get the total count of Expense entities"""
    count = database.query(Expense).count()
    return {"count": count}


@router.get("/expense/paginated/", response_model=None, tags=["Expense"])
def get_paginated_expense(skip: int = 0, limit: int = 100, detailed: bool = False, database: Session = Depends(get_db)) -> dict:
    """Get paginated list of Expense entities"""
    total = database.query(Expense).count()
    expense_list = database.query(Expense).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": expense_list
    }
@router.get("/expense/search/", response_model=None, tags=["Expense"])
def search_expense(
    amount: float = None,
    description: str = None,
    recurrenceIntervalMonths: int = None,
    database: Session = Depends(get_db)
) -> list:
    """Search Expense entities by attributes"""
    query = database.query(Expense)

    if amount is not None:
        query = query.filter(Expense.amount == amount)
    if description is not None:
        query = query.filter(Expense.description.ilike(f"%{description}%"))
    if recurrenceIntervalMonths is not None:
        query = query.filter(Expense.recurrenceIntervalMonths == recurrenceIntervalMonths)

    results = query.all()
    return results


@router.get("/expense/{expense_id}/", response_model=None, tags=["Expense"])
async def get_expense(expense_id: int, database: Session = Depends(get_db)) -> Expense:
    db_expense = database.query(Expense).filter(Expense.id == expense_id).first()
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    response_data = {
        "expense": db_expense,
}
    return response_data



@router.post("/expense/", response_model=None, tags=["Expense"])
async def create_expense(expense_data: ExpenseCreate, database: Session = Depends(get_db)) -> Expense:

    if expense_data.account is not None:
        related_account = database.query(Account).filter(Account.id == expense_data.account).first()
        if not related_account:
            raise HTTPException(status_code=400, detail="Account not found")
    else:
        raise HTTPException(status_code=400, detail="Account ID is required")
    if expense_data.category is not None:
        related_category = database.query(Category).filter(Category.id == expense_data.category).first()
        if not related_category:
            raise HTTPException(status_code=400, detail="Category not found")
        if related_category.kind != 'expense':
            raise HTTPException(status_code=422, detail='Expense requires an expense category')

    db_expense = Expense(
        amount=expense_data.amount if expense_data.amount is not None else expense_data.expectedValue,        description=expense_data.description,        endDate=expense_data.endDate,        recurrenceIntervalMonths=expense_data.recurrenceIntervalMonths,        startDate=expense_data.startDate,        expenseType=expense_data.expenseType.name,        expectedValue=expense_data.expectedValue,        allowedDeviation=expense_data.allowedDeviation,        account_id=expense_data.account,        category_id=expense_data.category        )

    database.add(db_expense)
    database.flush()
    database.refresh(db_expense)





    database.commit()
    database.refresh(db_expense)
    return db_expense


@router.post("/expense/bulk/", response_model=None, tags=["Expense"])
async def bulk_create_expense(items: list[ExpenseCreate], database: Session = Depends(get_db)) -> dict:
    """Create multiple Expense entities at once"""
    created_items = []
    errors = []

    for idx, item_data in enumerate(items):
        try:
            # Basic validation for each item
            if not item_data.account:
                raise ValueError("Account ID is required")
            if item_data.category is not None and (category := database.get(Category, item_data.category)) is None:
                raise ValueError("Category not found")
            if item_data.category is not None and category.kind != 'expense':
                raise ValueError('Expense requires an expense category')

            db_expense = Expense(
                amount=item_data.amount if item_data.amount is not None else item_data.expectedValue,                description=item_data.description,                endDate=item_data.endDate,                recurrenceIntervalMonths=item_data.recurrenceIntervalMonths,                startDate=item_data.startDate,                expenseType=item_data.expenseType.name,                expectedValue=item_data.expectedValue,                allowedDeviation=item_data.allowedDeviation,                account_id=item_data.account,                category_id=item_data.category            )
            database.add(db_expense)
            database.flush()  # Get ID without committing
            created_items.append(db_expense.id)
        except ValueError as e:
            errors.append({"index": idx, "error": str(e)})
        except IntegrityError as e:
            # The driver's text goes to the log; a failed flush ends the session's work.
            logger.error("Bulk creation of Expense failed at item %s: %s", idx, e)
            errors.append({"index": idx, "error": integrity_error_detail(e)})
            break

    if errors:
        database.rollback()
        raise HTTPException(status_code=400, detail={"message": "Bulk creation failed", "errors": errors})

    database.commit()
    return {
        "created_count": len(created_items),
        "created_ids": created_items,
        "message": f"Successfully created {len(created_items)} Expense entities"
    }


@router.delete("/expense/bulk/", response_model=None, tags=["Expense"])
async def bulk_delete_expense(ids: list[int], database: Session = Depends(get_db)) -> dict:
    """Delete multiple Expense entities at once"""
    deleted_count = 0
    not_found = []

    for item_id in ids:
        db_expense = database.query(Expense).filter(Expense.id == item_id).first()
        if db_expense:
            conflict = expense_delete_conflict(db_expense)
            if conflict:
                raise HTTPException(status_code=409, detail="Cannot delete Expense " + str(item_id) + ": " + conflict)
            database.query(OccurrenceAmount).filter_by(entry_id=item_id).delete()
            database.delete(db_expense)
            deleted_count += 1
        else:
            not_found.append(item_id)

    database.commit()

    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "message": f"Successfully deleted {deleted_count} Expense entities"
    }

@router.put("/expense/{expense_id}/", response_model=None, tags=["Expense"])
async def update_expense(expense_id: int, expense_data: ExpenseCreate, database: Session = Depends(get_db)) -> Expense:
    db_expense = database.query(Expense).filter(Expense.id == expense_id).first()
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    setattr(db_expense, 'amount', expense_data.amount if expense_data.amount is not None else expense_data.expectedValue)
    setattr(db_expense, 'description', expense_data.description)
    setattr(db_expense, 'endDate', expense_data.endDate)
    setattr(db_expense, 'recurrenceIntervalMonths', expense_data.recurrenceIntervalMonths)
    setattr(db_expense, 'startDate', expense_data.startDate)
    setattr(db_expense, 'expenseType', expense_data.expenseType.name)
    setattr(db_expense, 'expectedValue', expense_data.expectedValue)
    setattr(db_expense, 'allowedDeviation', expense_data.allowedDeviation)
    for field, model in [('account', Account), ('category', Category)]:
        related_id = getattr(expense_data, field)
        if (related_id is None and field == 'account') or (related_id is not None and database.get(model, related_id) is None):
            raise HTTPException(status_code=400, detail=f'{field.title()} not found')
        if field == 'category' and related_id is not None and database.get(Category, related_id).kind != 'expense':
            raise HTTPException(status_code=422, detail='Expense requires an expense category')
        setattr(db_expense, field + '_id', related_id)
    database.commit()
    database.refresh(db_expense)

    return db_expense


def expense_delete_conflict(db_expense, deleting=None, wholes=()):
    """Why this Expense cannot be deleted (None when it can): a related record
    would be left without a link it requires. Covers the parts deleted with it;
    ``deleting`` holds every record of the delete, since none of them can block it,
    and ``wholes`` the records on the way down to this part."""
    if deleting is None:
        state = sa_inspect(db_expense)
        deleting = [db_expense] + [item[0] for item in state.mapper.cascade_iterator("delete", state)]
    return None


@router.delete("/expense/{expense_id}/", response_model=None, tags=["Expense"])
async def delete_expense(expense_id: int, database: Session = Depends(get_db)):
    db_expense = database.query(Expense).filter(Expense.id == expense_id).first()
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    conflict = expense_delete_conflict(db_expense)
    if conflict:
        raise HTTPException(status_code=409, detail="Cannot delete Expense " + str(expense_id) + ": " + conflict)
    # Snapshot the columns before deleting: cascading the association-class
    # links loads relationship collections whose back-references would make
    # the JSON encoder recurse endlessly on the live object.
    deleted_expense = {
        attr.key: getattr(db_expense, attr.key)
        for attr in db_expense.__mapper__.column_attrs
    }
    database.query(OccurrenceAmount).filter_by(entry_id=expense_id).delete()
    database.delete(db_expense)
    database.commit()
    return deleted_expense



