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
from cashflow import project

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/accountgroup/", response_model=None, tags=["AccountGroup"])
def get_all_accountgroup(detailed: bool = False, database: Session = Depends(get_db)) -> list:
    # Use detailed=true to get entities with eagerly loaded relationships (for tables with lookup columns)
    if detailed:
        # Eagerly load all relationships to avoid N+1 queries
        query = database.query(AccountGroup)
        accountgroup_list = query.all()

        # Serialize with relationships included
        result = []
        for db_accountgroup in accountgroup_list:
            item_dict = db_accountgroup.__dict__.copy()
            item_dict.pop('_sa_instance_state', None)

            # Add many-to-one relationships (foreign keys for lookup columns)

            # Add many-to-many and one-to-many relationship objects (full details)
            related_account_list = database.query(Account).join(groups, Account.id == groups.c["accounts"]).filter(groups.c["groups"] == db_accountgroup.id).all()
            item_dict['accounts'] = []
            for related_account_obj in related_account_list:
                related_account_dict = related_account_obj.__dict__.copy()
                related_account_dict.pop('_sa_instance_state', None)
                item_dict['accounts'].append(related_account_dict)

            result.append(item_dict)
        return result
    else:
        # Default: return flat entities (faster for charts/widgets without lookup columns)
        return database.query(AccountGroup).all()


@router.get("/accountgroup/count/", response_model=None, tags=["AccountGroup"])
def get_count_accountgroup(database: Session = Depends(get_db)) -> dict:
    """Get the total count of AccountGroup entities"""
    count = database.query(AccountGroup).count()
    return {"count": count}


@router.get("/accountgroup/paginated/", response_model=None, tags=["AccountGroup"])
def get_paginated_accountgroup(skip: int = 0, limit: int = 100, detailed: bool = False, database: Session = Depends(get_db)) -> dict:
    """Get paginated list of AccountGroup entities"""
    total = database.query(AccountGroup).count()
    accountgroup_list = database.query(AccountGroup).offset(skip).limit(limit).all()
    # By default, return flat entities (for charts/widgets)
    # Use detailed=true to get entities with relationships
    if not detailed:
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "data": accountgroup_list
        }

    result = []
    for db_accountgroup in accountgroup_list:
        related_account_ids = database.query(groups.c["accounts"]).filter(groups.c["groups"] == db_accountgroup.id).all()
        item_data = {
            "accountgroup": db_accountgroup,
            "account_ids": [x[0] for x in related_account_ids],
        }
        result.append(item_data)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": result
    }
@router.get("/accountgroup/search/", response_model=None, tags=["AccountGroup"])
def search_accountgroup(
    name: str = None,
    database: Session = Depends(get_db)
) -> list:
    """Search AccountGroup entities by attributes"""
    query = database.query(AccountGroup)

    if name is not None:
        query = query.filter(AccountGroup.name.ilike(f"%{name}%"))

    results = query.all()
    return results


@router.get('/accountgroup/{accountgroup_id}/cashflow/', tags=['AccountGroup'])
def group_cashflow(accountgroup_id: int, months: int = 12, database: Session = Depends(get_db)):
    if not 1 <= months <= 60:
        raise HTTPException(status_code=422, detail='Months must be between 1 and 60')
    group = database.get(AccountGroup, accountgroup_id)
    if group is None:
        raise HTTPException(status_code=404, detail='AccountGroup not found')
    accounts = group.accounts
    currencies = {account.currency for account in accounts}
    if len(currencies) > 1:
        raise HTTPException(status_code=422, detail='Consolidated accounts must share a currency')
    return {'accountgroup_id': accountgroup_id, 'account_ids': [a.id for a in accounts],
            'currency': next(iter(currencies)), 'months': project(database, accounts, months)}


@router.get("/accountgroup/{accountgroup_id}/", response_model=None, tags=["AccountGroup"])
async def get_accountgroup(accountgroup_id: int, database: Session = Depends(get_db)) -> AccountGroup:
    db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if db_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")

    related_account_ids = database.query(groups.c["accounts"]).filter(groups.c["groups"] == db_accountgroup.id).all()
    response_data = {
        "accountgroup": db_accountgroup,
        "account_ids": [x[0] for x in related_account_ids],
}
    return response_data



@router.post("/accountgroup/", response_model=None, tags=["AccountGroup"])
async def create_accountgroup(accountgroup_data: AccountGroupCreate, database: Session = Depends(get_db)) -> AccountGroup:

    if not accountgroup_data.accounts or len(accountgroup_data.accounts) < 1:
        raise HTTPException(status_code=400, detail="At least 1 Account(s) required")
    if accountgroup_data.accounts:
        for id in accountgroup_data.accounts:
            # Entity already validated before creation
            related_account = database.query(Account).filter(Account.id == id).first()
            if not related_account:
                raise HTTPException(status_code=404, detail=f"Account with ID {id} not found")

    db_accountgroup = AccountGroup(
        name=accountgroup_data.name        )

    database.add(db_accountgroup)
    database.flush()
    database.refresh(db_accountgroup)



    if accountgroup_data.accounts:
        for id in accountgroup_data.accounts:
            # Entity already validated before creation
            related_account = database.query(Account).filter(Account.id == id).first()
            # Create the association
            association = groups.insert().values(groups=db_accountgroup.id, accounts=related_account.id)
            database.execute(association)
            database.flush()


    related_account_ids = database.query(groups.c["accounts"]).filter(groups.c["groups"] == db_accountgroup.id).all()
    response_data = {
        "accountgroup": db_accountgroup,
        "account_ids": [x[0] for x in related_account_ids],
    }
    database.commit()
    database.refresh(db_accountgroup)
    return response_data


@router.post("/accountgroup/bulk/", response_model=None, tags=["AccountGroup"])
async def bulk_create_accountgroup(items: list[AccountGroupCreate], database: Session = Depends(get_db)) -> dict:
    """Create multiple AccountGroup entities at once"""
    if items:
        raise HTTPException(status_code=422, detail="Bulk creation of AccountGroup with required relationships is not supported; use POST /accountgroup/ to validate and persist its relationships")
    created_items = []
    errors = []

    for idx, item_data in enumerate(items):
        try:
            # Basic validation for each item

            db_accountgroup = AccountGroup(
                name=item_data.name            )
            database.add(db_accountgroup)
            database.flush()  # Get ID without committing
            created_items.append(db_accountgroup.id)
        except ValueError as e:
            errors.append({"index": idx, "error": str(e)})
        except IntegrityError as e:
            # The driver's text goes to the log; a failed flush ends the session's work.
            logger.error("Bulk creation of AccountGroup failed at item %s: %s", idx, e)
            errors.append({"index": idx, "error": integrity_error_detail(e)})
            break

    if errors:
        database.rollback()
        raise HTTPException(status_code=400, detail={"message": "Bulk creation failed", "errors": errors})

    database.commit()
    return {
        "created_count": len(created_items),
        "created_ids": created_items,
        "message": f"Successfully created {len(created_items)} AccountGroup entities"
    }


@router.delete("/accountgroup/bulk/", response_model=None, tags=["AccountGroup"])
async def bulk_delete_accountgroup(ids: list[int], database: Session = Depends(get_db)) -> dict:
    """Delete multiple AccountGroup entities at once"""
    deleted_count = 0
    not_found = []

    for item_id in ids:
        db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == item_id).first()
        if db_accountgroup:
            conflict = accountgroup_delete_conflict(db_accountgroup)
            if conflict:
                raise HTTPException(status_code=409, detail="Cannot delete AccountGroup " + str(item_id) + ": " + conflict)
            database.delete(db_accountgroup)
            deleted_count += 1
        else:
            not_found.append(item_id)

    database.commit()

    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "message": f"Successfully deleted {deleted_count} AccountGroup entities"
    }

@router.put("/accountgroup/{accountgroup_id}/", response_model=None, tags=["AccountGroup"])
async def update_accountgroup(accountgroup_id: int, accountgroup_data: AccountGroupCreate, database: Session = Depends(get_db)) -> AccountGroup:
    db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if db_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")

    setattr(db_accountgroup, 'name', accountgroup_data.name)
    if accountgroup_data.accounts is not None:
        if len(accountgroup_data.accounts) < 1:
            raise HTTPException(status_code=400, detail="At least 1 Account(s) required")
        existing_related_account_ids = [assoc._mapping["accounts"] for assoc in database.execute(
            groups.select().where(groups.c["groups"] == db_accountgroup.id))]

        related_accounts_to_remove = set(existing_related_account_ids) - set(accountgroup_data.accounts)
        for related_account_id in related_accounts_to_remove:
            association = groups.delete().where(
                (groups.c["groups"] == db_accountgroup.id) & (groups.c["accounts"] == related_account_id))
            database.execute(association)

        new_related_account_ids = set(accountgroup_data.accounts) - set(existing_related_account_ids)
        for related_account_id in new_related_account_ids:
            related_account = database.query(Account).filter(Account.id == related_account_id).first()
            if related_account is None:
                raise HTTPException(status_code=404, detail="Account with ID " + str(related_account_id) + " not found")
            association = groups.insert().values(accounts=related_account.id, groups=db_accountgroup.id)
            database.execute(association)
    database.commit()
    database.refresh(db_accountgroup)

    related_account_ids = database.query(groups.c["accounts"]).filter(groups.c["groups"] == db_accountgroup.id).all()
    response_data = {
        "accountgroup": db_accountgroup,
        "account_ids": [x[0] for x in related_account_ids],
    }
    return response_data


def accountgroup_delete_conflict(db_accountgroup, deleting=None, wholes=()):
    """Why this AccountGroup cannot be deleted (None when it can): a related record
    would be left without a link it requires. Covers the parts deleted with it;
    ``deleting`` holds every record of the delete, since none of them can block it,
    and ``wholes`` the records on the way down to this part."""
    if deleting is None:
        state = sa_inspect(db_accountgroup)
        deleting = [db_accountgroup] + [item[0] for item in state.mapper.cascade_iterator("delete", state)]
    return None


@router.delete("/accountgroup/{accountgroup_id}/", response_model=None, tags=["AccountGroup"])
async def delete_accountgroup(accountgroup_id: int, database: Session = Depends(get_db)):
    db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if db_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")
    conflict = accountgroup_delete_conflict(db_accountgroup)
    if conflict:
        raise HTTPException(status_code=409, detail="Cannot delete AccountGroup " + str(accountgroup_id) + ": " + conflict)
    # Snapshot the columns before deleting: cascading the association-class
    # links loads relationship collections whose back-references would make
    # the JSON encoder recurse endlessly on the live object.
    deleted_accountgroup = {
        attr.key: getattr(db_accountgroup, attr.key)
        for attr in db_accountgroup.__mapper__.column_attrs
    }
    database.delete(db_accountgroup)
    database.commit()
    return deleted_accountgroup

@router.post("/accountgroup/{accountgroup_id}/accounts/{account_id}/", response_model=None, tags=["AccountGroup Relationships"])
async def add_accounts_to_accountgroup(accountgroup_id: int, account_id: int, database: Session = Depends(get_db)):
    """Add a Account to this AccountGroup's accounts relationship"""
    db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if db_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")

    related_account = database.query(Account).filter(Account.id == account_id).first()
    if related_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    # Check if relationship already exists
    existing = database.query(groups).filter(
        (groups.c["groups"] == accountgroup_id) &
        (groups.c["accounts"] == account_id)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    # Create the association
    association = groups.insert().values(groups=accountgroup_id, accounts=account_id)
    database.execute(association)
    database.commit()

    return {"message": "Account added to accounts successfully"}


@router.delete("/accountgroup/{accountgroup_id}/accounts/{account_id}/", response_model=None, tags=["AccountGroup Relationships"])
async def remove_accounts_from_accountgroup(accountgroup_id: int, account_id: int, database: Session = Depends(get_db)):
    """Remove a Account from this AccountGroup's accounts relationship"""
    db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if db_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")

    # Check if relationship exists
    existing = database.query(groups).filter(
        (groups.c["groups"] == accountgroup_id) &
        (groups.c["accounts"] == account_id)
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Relationship not found")

    if len(db_accountgroup.accounts) - 1 < 1:
        raise HTTPException(status_code=409, detail="AccountGroup " + str(accountgroup_id) + " requires at least 1 accounts")

    # Delete the association
    association = groups.delete().where(
        (groups.c["groups"] == accountgroup_id) &
        (groups.c["accounts"] == account_id)
    )
    database.execute(association)
    database.commit()

    return {"message": "Account removed from accounts successfully"}


@router.get("/accountgroup/{accountgroup_id}/accounts/", response_model=None, tags=["AccountGroup Relationships"])
async def get_accounts_of_accountgroup(accountgroup_id: int, database: Session = Depends(get_db)):
    """Get all Account entities related to this AccountGroup through accounts"""
    db_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if db_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")

    related_account_ids = database.query(groups.c["accounts"]).filter(groups.c["groups"] == accountgroup_id).all()
    related_account_list = database.query(Account).filter(Account.id.in_([id[0] for id in related_account_ids])).all()

    return {
        "accountgroup_id": accountgroup_id,
        "accounts_count": len(related_account_list),
        "accounts": related_account_list
    }



