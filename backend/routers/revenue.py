import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from pydantic_classes import *
from sql_alchemy import *
from database import get_db, integrity_error_detail
from bal_stdlib import *

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/revenue/", response_model=None, tags=["Revenue"])
def get_all_revenue(detailed: bool = False, database: Session = Depends(get_db)) -> list:
    # Use detailed=true to get entities with eagerly loaded relationships (for tables with lookup columns)
    if detailed:
        # Eagerly load all relationships to avoid N+1 queries
        query = database.query(Revenue)
        query = query.options(joinedload(Revenue.account))
        query = query.options(joinedload(Revenue.category))
        revenue_list = query.all()

        # Serialize with relationships included
        result = []
        for db_revenue in revenue_list:
            item_dict = db_revenue.__dict__.copy()
            item_dict.pop('_sa_instance_state', None)

            # Add many-to-one relationships (foreign keys for lookup columns)
            if db_revenue.account:
                related_obj = db_revenue.account
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['account'] = related_dict
            else:
                item_dict['account'] = None
            if db_revenue.category:
                related_obj = db_revenue.category
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['category'] = related_dict
            else:
                item_dict['category'] = None


            result.append(item_dict)
        return result
    else:
        # Default: return flat entities (faster for charts/widgets without lookup columns)
        return database.query(Revenue).all()


@router.get("/revenue/count/", response_model=None, tags=["Revenue"])
def get_count_revenue(database: Session = Depends(get_db)) -> dict:
    """Get the total count of Revenue entities"""
    count = database.query(Revenue).count()
    return {"count": count}


@router.get("/revenue/paginated/", response_model=None, tags=["Revenue"])
def get_paginated_revenue(skip: int = 0, limit: int = 100, detailed: bool = False, database: Session = Depends(get_db)) -> dict:
    """Get paginated list of Revenue entities"""
    total = database.query(Revenue).count()
    revenue_list = database.query(Revenue).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": revenue_list
    }
@router.get("/revenue/search/", response_model=None, tags=["Revenue"])
def search_revenue(
    amount: float = None,
    description: str = None,
    recurrenceIntervalMonths: int = None,
    database: Session = Depends(get_db)
) -> list:
    """Search Revenue entities by attributes"""
    query = database.query(Revenue)

    if amount is not None:
        query = query.filter(Revenue.amount == amount)
    if description is not None:
        query = query.filter(Revenue.description.ilike(f"%{description}%"))
    if recurrenceIntervalMonths is not None:
        query = query.filter(Revenue.recurrenceIntervalMonths == recurrenceIntervalMonths)

    results = query.all()
    return results


@router.get("/revenue/{revenue_id}/", response_model=None, tags=["Revenue"])
async def get_revenue(revenue_id: int, database: Session = Depends(get_db)) -> Revenue:
    db_revenue = database.query(Revenue).filter(Revenue.id == revenue_id).first()
    if db_revenue is None:
        raise HTTPException(status_code=404, detail="Revenue not found")

    response_data = {
        "revenue": db_revenue,
}
    return response_data



@router.post("/revenue/", response_model=None, tags=["Revenue"])
async def create_revenue(revenue_data: RevenueCreate, database: Session = Depends(get_db)) -> Revenue:

    if revenue_data.account is not None:
        related_account = database.query(Account).filter(Account.id == revenue_data.account).first()
        if not related_account:
            raise HTTPException(status_code=400, detail="Account not found")
    else:
        raise HTTPException(status_code=400, detail="Account ID is required")
    if revenue_data.category is not None:
        related_category = database.query(Category).filter(Category.id == revenue_data.category).first()
        if not related_category:
            raise HTTPException(status_code=400, detail="Category not found")
    else:
        raise HTTPException(status_code=400, detail="Category ID is required")

    db_revenue = Revenue(
        amount=revenue_data.amount,        description=revenue_data.description,        endDate=revenue_data.endDate,        recurrenceIntervalMonths=revenue_data.recurrenceIntervalMonths,        startDate=revenue_data.startDate,        account_id=revenue_data.account,        category_id=revenue_data.category        )

    database.add(db_revenue)
    database.flush()
    database.refresh(db_revenue)





    database.commit()
    database.refresh(db_revenue)
    return db_revenue


@router.post("/revenue/bulk/", response_model=None, tags=["Revenue"])
async def bulk_create_revenue(items: list[RevenueCreate], database: Session = Depends(get_db)) -> dict:
    """Create multiple Revenue entities at once"""
    created_items = []
    errors = []

    for idx, item_data in enumerate(items):
        try:
            # Basic validation for each item
            if not item_data.account:
                raise ValueError("Account ID is required")
            if not item_data.category:
                raise ValueError("Category ID is required")

            db_revenue = Revenue(
                amount=item_data.amount,                description=item_data.description,                endDate=item_data.endDate,                recurrenceIntervalMonths=item_data.recurrenceIntervalMonths,                startDate=item_data.startDate,                account_id=item_data.account,                category_id=item_data.category            )
            database.add(db_revenue)
            database.flush()  # Get ID without committing
            created_items.append(db_revenue.id)
        except ValueError as e:
            errors.append({"index": idx, "error": str(e)})
        except IntegrityError as e:
            # The driver's text goes to the log; a failed flush ends the session's work.
            logger.error("Bulk creation of Revenue failed at item %s: %s", idx, e)
            errors.append({"index": idx, "error": integrity_error_detail(e)})
            break

    if errors:
        database.rollback()
        raise HTTPException(status_code=400, detail={"message": "Bulk creation failed", "errors": errors})

    database.commit()
    return {
        "created_count": len(created_items),
        "created_ids": created_items,
        "message": f"Successfully created {len(created_items)} Revenue entities"
    }


@router.delete("/revenue/bulk/", response_model=None, tags=["Revenue"])
async def bulk_delete_revenue(ids: list[int], database: Session = Depends(get_db)) -> dict:
    """Delete multiple Revenue entities at once"""
    deleted_count = 0
    not_found = []

    for item_id in ids:
        db_revenue = database.query(Revenue).filter(Revenue.id == item_id).first()
        if db_revenue:
            conflict = revenue_delete_conflict(db_revenue)
            if conflict:
                raise HTTPException(status_code=409, detail="Cannot delete Revenue " + str(item_id) + ": " + conflict)
            database.delete(db_revenue)
            deleted_count += 1
        else:
            not_found.append(item_id)

    database.commit()

    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "message": f"Successfully deleted {deleted_count} Revenue entities"
    }

@router.put("/revenue/{revenue_id}/", response_model=None, tags=["Revenue"])
async def update_revenue(revenue_id: int, revenue_data: RevenueCreate, database: Session = Depends(get_db)) -> Revenue:
    db_revenue = database.query(Revenue).filter(Revenue.id == revenue_id).first()
    if db_revenue is None:
        raise HTTPException(status_code=404, detail="Revenue not found")

    setattr(db_revenue, 'amount', revenue_data.amount)
    setattr(db_revenue, 'description', revenue_data.description)
    setattr(db_revenue, 'endDate', revenue_data.endDate)
    setattr(db_revenue, 'recurrenceIntervalMonths', revenue_data.recurrenceIntervalMonths)
    setattr(db_revenue, 'startDate', revenue_data.startDate)
    for field, model in [('account', Account), ('category', Category)]:
        related_id = getattr(revenue_data, field)
        if database.get(model, related_id) is None:
            raise HTTPException(status_code=400, detail=f'{field.title()} not found')
        setattr(db_revenue, field + '_id', related_id)
    database.commit()
    database.refresh(db_revenue)

    return db_revenue


def revenue_delete_conflict(db_revenue, deleting=None, wholes=()):
    """Why this Revenue cannot be deleted (None when it can): a related record
    would be left without a link it requires. Covers the parts deleted with it;
    ``deleting`` holds every record of the delete, since none of them can block it,
    and ``wholes`` the records on the way down to this part."""
    if deleting is None:
        state = sa_inspect(db_revenue)
        deleting = [db_revenue] + [item[0] for item in state.mapper.cascade_iterator("delete", state)]
    return None


@router.delete("/revenue/{revenue_id}/", response_model=None, tags=["Revenue"])
async def delete_revenue(revenue_id: int, database: Session = Depends(get_db)):
    db_revenue = database.query(Revenue).filter(Revenue.id == revenue_id).first()
    if db_revenue is None:
        raise HTTPException(status_code=404, detail="Revenue not found")
    conflict = revenue_delete_conflict(db_revenue)
    if conflict:
        raise HTTPException(status_code=409, detail="Cannot delete Revenue " + str(revenue_id) + ": " + conflict)
    # Snapshot the columns before deleting: cascading the association-class
    # links loads relationship collections whose back-references would make
    # the JSON encoder recurse endlessly on the live object.
    deleted_revenue = {
        attr.key: getattr(db_revenue, attr.key)
        for attr in db_revenue.__mapper__.column_attrs
    }
    database.delete(db_revenue)
    database.commit()
    return deleted_revenue



