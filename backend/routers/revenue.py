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


@router.get("/income/", response_model=None, tags=["Income"])
def get_all_income(detailed: bool = False, database: Session = Depends(get_db)) -> list:
    # Use detailed=true to get entities with eagerly loaded relationships (for tables with lookup columns)
    if detailed:
        # Eagerly load all relationships to avoid N+1 queries
        query = database.query(Income)
        query = query.options(joinedload(Income.account))
        query = query.options(joinedload(Income.category))
        income_list = query.all()

        # Serialize with relationships included
        result = []
        for db_income in income_list:
            item_dict = db_income.__dict__.copy()
            item_dict.pop('_sa_instance_state', None)

            # Add many-to-one relationships (foreign keys for lookup columns)
            if db_income.account:
                related_obj = db_income.account
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['account'] = related_dict
            else:
                item_dict['account'] = None
            if db_income.category:
                related_obj = db_income.category
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['category'] = related_dict
            else:
                item_dict['category'] = None


            result.append(item_dict)
        return result
    else:
        # Default: return flat entities (faster for charts/widgets without lookup columns)
        return database.query(Income).all()


@router.get("/income/count/", response_model=None, tags=["Income"])
def get_count_income(database: Session = Depends(get_db)) -> dict:
    """Get the total count of Income entities"""
    count = database.query(Income).count()
    return {"count": count}


@router.get("/income/paginated/", response_model=None, tags=["Income"])
def get_paginated_income(skip: int = 0, limit: int = 100, detailed: bool = False, database: Session = Depends(get_db)) -> dict:
    """Get paginated list of Income entities"""
    total = database.query(Income).count()
    income_list = database.query(Income).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": income_list
    }
@router.get("/income/search/", response_model=None, tags=["Income"])
def search_income(
    amount: float = None,
    description: str = None,
    recurrenceIntervalMonths: int = None,
    database: Session = Depends(get_db)
) -> list:
    """Search Income entities by attributes"""
    query = database.query(Income)

    if amount is not None:
        query = query.filter(Income.amount == amount)
    if description is not None:
        query = query.filter(Income.description.ilike(f"%{description}%"))
    if recurrenceIntervalMonths is not None:
        query = query.filter(Income.recurrenceIntervalMonths == recurrenceIntervalMonths)

    results = query.all()
    return results


@router.get("/income/{income_id}/", response_model=None, tags=["Income"])
async def get_income(income_id: int, database: Session = Depends(get_db)) -> Income:
    db_income = database.query(Income).filter(Income.id == income_id).first()
    if db_income is None:
        raise HTTPException(status_code=404, detail="Income not found")

    response_data = {
        "income": db_income,
}
    return response_data



@router.post("/income/", response_model=None, tags=["Income"])
async def create_income(income_data: IncomeCreate, database: Session = Depends(get_db)) -> Income:

    if income_data.account is not None:
        related_account = database.query(Account).filter(Account.id == income_data.account).first()
        if not related_account:
            raise HTTPException(status_code=400, detail="Account not found")
    else:
        raise HTTPException(status_code=400, detail="Account ID is required")
    if income_data.category is not None:
        related_category = database.query(Category).filter(Category.id == income_data.category).first()
        if not related_category:
            raise HTTPException(status_code=400, detail="Category not found")
        if related_category.kind != 'income':
            raise HTTPException(status_code=422, detail='Income requires an income category')

    db_income = Income(
        amount=income_data.amount if income_data.amount is not None else income_data.expectedValue,        description=income_data.description,        endDate=income_data.endDate,        recurrenceIntervalMonths=income_data.recurrenceIntervalMonths,        startDate=income_data.startDate,        incomeType=income_data.incomeType.value,        expectedValue=income_data.expectedValue,        allowedDeviation=income_data.allowedDeviation,        account_id=income_data.account,        category_id=income_data.category        )

    database.add(db_income)
    database.flush()
    if income_data.incomeType == IncomeType.VARIABLE and income_data.amount is not None:
        database.add(OccurrenceAmount(entry_id=db_income.id, date=db_income.startDate, amount=income_data.amount))
    database.commit()
    database.refresh(db_income)
    return db_income


@router.post("/income/bulk/", response_model=None, tags=["Income"])
async def bulk_create_income(items: list[IncomeCreate], database: Session = Depends(get_db)) -> dict:
    """Create multiple Income entities at once"""
    created_items = []
    errors = []

    for idx, item_data in enumerate(items):
        try:
            # Basic validation for each item
            if database.get(Account, item_data.account) is None:
                raise ValueError("Account not found")
            if item_data.category is not None and (category := database.get(Category, item_data.category)) is None:
                raise ValueError("Category not found")
            if item_data.category is not None and category.kind != 'income':
                raise ValueError('Income requires an income category')

            db_income = Income(
                amount=item_data.amount if item_data.amount is not None else item_data.expectedValue,                description=item_data.description,                endDate=item_data.endDate,                recurrenceIntervalMonths=item_data.recurrenceIntervalMonths,                startDate=item_data.startDate,                incomeType=item_data.incomeType.value,                expectedValue=item_data.expectedValue,                allowedDeviation=item_data.allowedDeviation,                account_id=item_data.account,                category_id=item_data.category            )
            database.add(db_income)
            database.flush()  # Get ID without committing
            if item_data.incomeType == IncomeType.VARIABLE and item_data.amount is not None:
                database.add(OccurrenceAmount(entry_id=db_income.id, date=db_income.startDate, amount=item_data.amount))
            created_items.append(db_income.id)
        except ValueError as e:
            errors.append({"index": idx, "error": str(e)})
        except IntegrityError as e:
            # The driver's text goes to the log; a failed flush ends the session's work.
            logger.error("Bulk creation of Income failed at item %s: %s", idx, e)
            errors.append({"index": idx, "error": integrity_error_detail(e)})
            break

    if errors:
        database.rollback()
        raise HTTPException(status_code=400, detail={"message": "Bulk creation failed", "errors": errors})

    database.commit()
    return {
        "created_count": len(created_items),
        "created_ids": created_items,
        "message": f"Successfully created {len(created_items)} Income entities"
    }


@router.delete("/income/bulk/", response_model=None, tags=["Income"])
async def bulk_delete_income(ids: list[int], database: Session = Depends(get_db)) -> dict:
    """Delete multiple Income entities at once"""
    deleted_count = 0
    not_found = []

    for item_id in ids:
        db_income = database.query(Income).filter(Income.id == item_id).first()
        if db_income:
            conflict = income_delete_conflict(db_income)
            if conflict:
                raise HTTPException(status_code=409, detail="Cannot delete Income " + str(item_id) + ": " + conflict)
            database.query(OccurrenceAmount).filter_by(entry_id=item_id).delete()
            database.delete(db_income)
            deleted_count += 1
        else:
            not_found.append(item_id)

    database.commit()

    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "message": f"Successfully deleted {deleted_count} Income entities"
    }

@router.put("/income/{income_id}/", response_model=None, tags=["Income"])
async def update_income(income_id: int, income_data: IncomeCreate, database: Session = Depends(get_db)) -> Income:
    db_income = database.query(Income).filter(Income.id == income_id).first()
    if db_income is None:
        raise HTTPException(status_code=404, detail="Income not found")

    setattr(db_income, 'amount', income_data.amount if income_data.amount is not None else income_data.expectedValue)
    setattr(db_income, 'description', income_data.description)
    setattr(db_income, 'endDate', income_data.endDate)
    setattr(db_income, 'recurrenceIntervalMonths', income_data.recurrenceIntervalMonths)
    setattr(db_income, 'startDate', income_data.startDate)
    setattr(db_income, 'incomeType', income_data.incomeType.value)
    setattr(db_income, 'expectedValue', income_data.expectedValue)
    setattr(db_income, 'allowedDeviation', income_data.allowedDeviation)
    for field, model in [('account', Account), ('category', Category)]:
        related_id = getattr(income_data, field)
        if (related_id is None and field == 'account') or (related_id is not None and database.get(model, related_id) is None):
            raise HTTPException(status_code=400, detail=f'{field.title()} not found')
        if field == 'category' and related_id is not None and database.get(Category, related_id).kind != 'income':
            raise HTTPException(status_code=422, detail='Income requires an income category')
        setattr(db_income, field + '_id', related_id)
    if income_data.incomeType == IncomeType.VARIABLE:
        initial = database.get(OccurrenceAmount, (income_id, income_data.startDate))
        if income_data.amount is not None:
            if initial is None:
                database.add(OccurrenceAmount(entry_id=income_id, date=income_data.startDate, amount=income_data.amount))
            else:
                initial.amount = income_data.amount
        elif initial is not None:
            database.delete(initial)
    database.commit()
    database.refresh(db_income)

    return db_income


def income_delete_conflict(db_income, deleting=None, wholes=()):
    """Why this Income cannot be deleted (None when it can): a related record
    would be left without a link it requires. Covers the parts deleted with it;
    ``deleting`` holds every record of the delete, since none of them can block it,
    and ``wholes`` the records on the way down to this part."""
    if deleting is None:
        state = sa_inspect(db_income)
        deleting = [db_income] + [item[0] for item in state.mapper.cascade_iterator("delete", state)]
    return None


@router.delete("/income/{income_id}/", response_model=None, tags=["Income"])
async def delete_income(income_id: int, database: Session = Depends(get_db)):
    db_income = database.query(Income).filter(Income.id == income_id).first()
    if db_income is None:
        raise HTTPException(status_code=404, detail="Income not found")
    conflict = income_delete_conflict(db_income)
    if conflict:
        raise HTTPException(status_code=409, detail="Cannot delete Income " + str(income_id) + ": " + conflict)
    # Snapshot the columns before deleting: cascading the association-class
    # links loads relationship collections whose back-references would make
    # the JSON encoder recurse endlessly on the live object.
    deleted_income = {
        attr.key: getattr(db_income, attr.key)
        for attr in db_income.__mapper__.column_attrs
    }
    database.query(OccurrenceAmount).filter_by(entry_id=income_id).delete()
    database.delete(db_income)
    database.commit()
    return deleted_income



