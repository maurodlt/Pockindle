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


@router.get("/entry/", response_model=None, tags=["Entry"])
def get_all_entry(detailed: bool = False, database: Session = Depends(get_db)) -> list:
    # Use detailed=true to get entities with eagerly loaded relationships (for tables with lookup columns)
    if detailed:
        # Eagerly load all relationships to avoid N+1 queries
        query = database.query(Entry)
        query = query.options(joinedload(Entry.account))
        query = query.options(joinedload(Entry.category))
        entry_list = query.all()

        # Serialize with relationships included
        result = []
        for db_entry in entry_list:
            item_dict = db_entry.__dict__.copy()
            item_dict.pop('_sa_instance_state', None)

            # Add many-to-one relationships (foreign keys for lookup columns)
            if db_entry.account:
                related_obj = db_entry.account
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['account'] = related_dict
            else:
                item_dict['account'] = None
            if db_entry.category:
                related_obj = db_entry.category
                related_dict = related_obj.__dict__.copy()
                related_dict.pop('_sa_instance_state', None)
                item_dict['category'] = related_dict
            else:
                item_dict['category'] = None


            result.append(item_dict)
        return result
    else:
        # Default: return flat entities (faster for charts/widgets without lookup columns)
        return database.query(Entry).all()


@router.get("/entry/count/", response_model=None, tags=["Entry"])
def get_count_entry(database: Session = Depends(get_db)) -> dict:
    """Get the total count of Entry entities"""
    count = database.query(Entry).count()
    return {"count": count}


@router.get("/entry/paginated/", response_model=None, tags=["Entry"])
def get_paginated_entry(skip: int = 0, limit: int = 100, detailed: bool = False, database: Session = Depends(get_db)) -> dict:
    """Get paginated list of Entry entities"""
    total = database.query(Entry).count()
    entry_list = database.query(Entry).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": entry_list
    }
@router.get("/entry/search/", response_model=None, tags=["Entry"])
def search_entry(
    amount: float = None,
    description: str = None,
    recurrenceIntervalMonths: int = None,
    database: Session = Depends(get_db)
) -> list:
    """Search Entry entities by attributes"""
    query = database.query(Entry)

    if amount is not None:
        query = query.filter(Entry.amount == amount)
    if description is not None:
        query = query.filter(Entry.description.ilike(f"%{description}%"))
    if recurrenceIntervalMonths is not None:
        query = query.filter(Entry.recurrenceIntervalMonths == recurrenceIntervalMonths)

    results = query.all()
    return results


@router.get("/entry/{entry_id}/", response_model=None, tags=["Entry"])
async def get_entry(entry_id: int, database: Session = Depends(get_db)) -> Entry:
    db_entry = database.query(Entry).filter(Entry.id == entry_id).first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    response_data = {
        "entry": db_entry,
}
    return response_data






@router.delete("/entry/bulk/", response_model=None, tags=["Entry"])
async def bulk_delete_entry(ids: list[int], database: Session = Depends(get_db)) -> dict:
    """Delete multiple Entry entities at once"""
    deleted_count = 0
    not_found = []

    for item_id in ids:
        db_entry = database.query(Entry).filter(Entry.id == item_id).first()
        if db_entry:
            conflict = entry_delete_conflict(db_entry)
            if conflict:
                raise HTTPException(status_code=409, detail="Cannot delete Entry " + str(item_id) + ": " + conflict)
            database.delete(db_entry)
            deleted_count += 1
        else:
            not_found.append(item_id)

    database.commit()

    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "message": f"Successfully deleted {deleted_count} Entry entities"
    }

@router.put("/entry/{entry_id}/", response_model=None, tags=["Entry"])
async def update_entry(entry_id: int, entry_data: EntryCreate, database: Session = Depends(get_db)) -> Entry:
    db_entry = database.query(Entry).filter(Entry.id == entry_id).first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    setattr(db_entry, 'amount', entry_data.amount)
    setattr(db_entry, 'description', entry_data.description)
    setattr(db_entry, 'endDate', entry_data.endDate)
    setattr(db_entry, 'recurrenceIntervalMonths', entry_data.recurrenceIntervalMonths)
    setattr(db_entry, 'startDate', entry_data.startDate)
    if entry_data.account is not None:
        related_account = database.query(Account).filter(Account.id == entry_data.account).first()
        if not related_account:
            raise HTTPException(status_code=400, detail="Account not found")
        setattr(db_entry, 'account_id', entry_data.account)
    if entry_data.category is not None:
        category = database.get(Category, entry_data.category)
        if category is None:
            raise HTTPException(status_code=400, detail="Category not found")
        if category.kind != db_entry.type_spec:
            raise HTTPException(status_code=422, detail='Category type must match entry type')
    setattr(db_entry, 'category_id', entry_data.category)
    database.commit()
    database.refresh(db_entry)

    return db_entry


def entry_delete_conflict(db_entry, deleting=None, wholes=()):
    """Why this Entry cannot be deleted (None when it can): a related record
    would be left without a link it requires. Covers the parts deleted with it;
    ``deleting`` holds every record of the delete, since none of them can block it,
    and ``wholes`` the records on the way down to this part."""
    if deleting is None:
        state = sa_inspect(db_entry)
        deleting = [db_entry] + [item[0] for item in state.mapper.cascade_iterator("delete", state)]
    return None


@router.delete("/entry/{entry_id}/", response_model=None, tags=["Entry"])
async def delete_entry(entry_id: int, database: Session = Depends(get_db)):
    db_entry = database.query(Entry).filter(Entry.id == entry_id).first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    conflict = entry_delete_conflict(db_entry)
    if conflict:
        raise HTTPException(status_code=409, detail="Cannot delete Entry " + str(entry_id) + ": " + conflict)
    # Snapshot the columns before deleting: cascading the association-class
    # links loads relationship collections whose back-references would make
    # the JSON encoder recurse endlessly on the live object.
    deleted_entry = {
        attr.key: getattr(db_entry, attr.key)
        for attr in db_entry.__mapper__.column_attrs
    }
    database.delete(db_entry)
    database.commit()
    return deleted_entry



