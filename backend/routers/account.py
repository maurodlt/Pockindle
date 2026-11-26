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
from sql_alchemy import Transfer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/account/", response_model=None, tags=["Account"])
def get_all_account(detailed: bool = False, database: Session = Depends(get_db)) -> list:
    # Use detailed=true to get entities with eagerly loaded relationships (for tables with lookup columns)
    if detailed:
        # Eagerly load all relationships to avoid N+1 queries
        query = database.query(Account)
        account_list = query.all()

        # Serialize with relationships included
        result = []
        for db_account in account_list:
            item_dict = db_account.__dict__.copy()
            item_dict.pop('_sa_instance_state', None)

            # Add many-to-one relationships (foreign keys for lookup columns)

            # Add many-to-many and one-to-many relationship objects (full details)
            related_accountgroup_list = database.query(AccountGroup).join(groups, AccountGroup.id == groups.c["groups"]).filter(groups.c["accounts"] == db_account.id).all()
            item_dict['groups'] = []
            for related_accountgroup_obj in related_accountgroup_list:
                related_accountgroup_dict = related_accountgroup_obj.__dict__.copy()
                related_accountgroup_dict.pop('_sa_instance_state', None)
                item_dict['groups'].append(related_accountgroup_dict)
            related_entry_list = database.query(Entry).filter(Entry.account_id == db_account.id).all()
            item_dict['entries'] = []
            for related_entry_obj in related_entry_list:
                related_entry_dict = related_entry_obj.__dict__.copy()
                related_entry_dict.pop('_sa_instance_state', None)
                item_dict['entries'].append(related_entry_dict)

            result.append(item_dict)
        return result
    else:
        # Default: return flat entities (faster for charts/widgets without lookup columns)
        return database.query(Account).all()


@router.get("/account/count/", response_model=None, tags=["Account"])
def get_count_account(database: Session = Depends(get_db)) -> dict:
    """Get the total count of Account entities"""
    count = database.query(Account).count()
    return {"count": count}


@router.get("/account/paginated/", response_model=None, tags=["Account"])
def get_paginated_account(skip: int = 0, limit: int = 100, detailed: bool = False, database: Session = Depends(get_db)) -> dict:
    """Get paginated list of Account entities"""
    total = database.query(Account).count()
    account_list = database.query(Account).offset(skip).limit(limit).all()
    # By default, return flat entities (for charts/widgets)
    # Use detailed=true to get entities with relationships
    if not detailed:
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "data": account_list
        }

    result = []
    for db_account in account_list:
        related_accountgroup_ids = database.query(groups.c["groups"]).filter(groups.c["accounts"] == db_account.id).all()
        entries_ids = database.query(Entry.id).filter(Entry.account_id == db_account.id).all()
        item_data = {
            "account": db_account,
            "accountgroup_ids": [x[0] for x in related_accountgroup_ids],
            "entries_ids": [x[0] for x in entries_ids]        }
        result.append(item_data)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": result
    }
@router.get("/account/search/", response_model=None, tags=["Account"])
def search_account(
    currency: str = None,
    name: str = None,
    openingBalance: float = None,
    database: Session = Depends(get_db)
) -> list:
    """Search Account entities by attributes"""
    query = database.query(Account)

    if currency is not None:
        query = query.filter(Account.currency.ilike(f"%{currency}%"))
    if name is not None:
        query = query.filter(Account.name.ilike(f"%{name}%"))
    if openingBalance is not None:
        query = query.filter(Account.openingBalance == openingBalance)

    results = query.all()
    return results


@router.get('/account/{account_id}/cashflow/', tags=['Account'])
def account_cashflow(account_id: int, months: int = 12, database: Session = Depends(get_db)):
    if not 1 <= months <= 60:
        raise HTTPException(status_code=422, detail='Months must be between 1 and 60')
    account = database.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    return {'account_id': account_id, 'currency': account.currency,
            'months': project(database, [account], months)}


@router.get("/account/{account_id}/", response_model=None, tags=["Account"])
async def get_account(account_id: int, database: Session = Depends(get_db)) -> Account:
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    related_accountgroup_ids = database.query(groups.c["groups"]).filter(groups.c["accounts"] == db_account.id).all()
    entries_ids = database.query(Entry.id).filter(Entry.account_id == db_account.id).all()
    response_data = {
        "account": db_account,
        "accountgroup_ids": [x[0] for x in related_accountgroup_ids],
        "entries_ids": [x[0] for x in entries_ids]}
    return response_data



@router.post("/account/", response_model=None, tags=["Account"])
async def create_account(account_data: AccountCreate, database: Session = Depends(get_db)) -> Account:

    if account_data.groups:
        for id in account_data.groups:
            # Entity already validated before creation
            related_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == id).first()
            if not related_accountgroup:
                raise HTTPException(status_code=404, detail=f"AccountGroup with ID {id} not found")
            if related_accountgroup.accounts and related_accountgroup.accounts[0].currency != account_data.currency:
                raise HTTPException(status_code=422, detail='Consolidated accounts must share a currency')

    db_account = Account(
        currency=account_data.currency,        name=account_data.name,        openingBalance=account_data.openingBalance,        openingBalanceDate=account_data.openingBalanceDate        )

    database.add(db_account)
    database.flush()
    database.refresh(db_account)

    if account_data.entries:
        # Validate that all Entry IDs exist
        for related_entry_id in account_data.entries:
            related_entry = database.query(Entry).filter(Entry.id == related_entry_id).first()
            if not related_entry:
                raise HTTPException(status_code=400, detail=f"Entry with id {related_entry_id} not found")

        # Update the related entities with the new foreign key
        database.query(Entry).filter(Entry.id.in_(account_data.entries)).update(
            {Entry.account_id: db_account.id}, synchronize_session=False
        )
        database.flush()


    if account_data.groups:
        for id in account_data.groups:
            # Entity already validated before creation
            related_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == id).first()
            # Create the association
            association = groups.insert().values(accounts=db_account.id, groups=related_accountgroup.id)
            database.execute(association)
            database.flush()


    related_accountgroup_ids = database.query(groups.c["groups"]).filter(groups.c["accounts"] == db_account.id).all()
    entries_ids = database.query(Entry.id).filter(Entry.account_id == db_account.id).all()
    response_data = {
        "account": db_account,
        "accountgroup_ids": [x[0] for x in related_accountgroup_ids],
        "entries_ids": [x[0] for x in entries_ids]    }
    database.commit()
    database.refresh(db_account)
    return response_data


@router.post("/account/bulk/", response_model=None, tags=["Account"])
async def bulk_create_account(items: list[AccountCreate], database: Session = Depends(get_db)) -> dict:
    """Create multiple Account entities at once"""
    if any(getattr(item, field, None) for item in items for field in ['groups', 'entries']):
        raise HTTPException(status_code=422, detail="Bulk creation of Account with relationships is not supported; use POST /account/ to validate and persist its relationships")
    created_items = []
    errors = []

    for idx, item_data in enumerate(items):
        try:
            # Basic validation for each item

            db_account = Account(
                currency=item_data.currency,                name=item_data.name,                openingBalance=item_data.openingBalance,                openingBalanceDate=item_data.openingBalanceDate            )
            database.add(db_account)
            database.flush()  # Get ID without committing
            created_items.append(db_account.id)
        except ValueError as e:
            errors.append({"index": idx, "error": str(e)})
        except IntegrityError as e:
            # The driver's text goes to the log; a failed flush ends the session's work.
            logger.error("Bulk creation of Account failed at item %s: %s", idx, e)
            errors.append({"index": idx, "error": integrity_error_detail(e)})
            break

    if errors:
        database.rollback()
        raise HTTPException(status_code=400, detail={"message": "Bulk creation failed", "errors": errors})

    database.commit()
    return {
        "created_count": len(created_items),
        "created_ids": created_items,
        "message": f"Successfully created {len(created_items)} Account entities"
    }


@router.delete("/account/bulk/", response_model=None, tags=["Account"])
async def bulk_delete_account(ids: list[int], database: Session = Depends(get_db)) -> dict:
    """Delete multiple Account entities at once"""
    # Aggregate deletion must account for every related lower bound. Until it
    # shares that validation, use the guarded individual delete endpoint.
    if ids:
        raise HTTPException(status_code=409, detail="Bulk deletion of Account can violate required relationships and is not supported; use the individual DELETE /account/ endpoint")
    deleted_count = 0
    not_found = []

    for item_id in ids:
        db_account = database.query(Account).filter(Account.id == item_id).first()
        if db_account:
            conflict = account_delete_conflict(db_account)
            if conflict:
                raise HTTPException(status_code=409, detail="Cannot delete Account " + str(item_id) + ": " + conflict)
            database.delete(db_account)
            deleted_count += 1
        else:
            not_found.append(item_id)

    database.commit()

    return {
        "deleted_count": deleted_count,
        "not_found": not_found,
        "message": f"Successfully deleted {deleted_count} Account entities"
    }

@router.put("/account/{account_id}/", response_model=None, tags=["Account"])
async def update_account(account_id: int, account_data: AccountCreate, database: Session = Depends(get_db)) -> Account:
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if any(a.currency != account_data.currency for group in db_account.groups for a in group.accounts if a.id != db_account.id):
        raise HTTPException(status_code=422, detail='Consolidated accounts must share a currency')
    if database.query(Transfer.id).filter(
        ((Transfer.fromAccount_id == account_id) & (Transfer.toAccount_id.in_(
            database.query(Account.id).filter(Account.currency != account_data.currency)))) |
        ((Transfer.toAccount_id == account_id) & (Transfer.fromAccount_id.in_(
            database.query(Account.id).filter(Account.currency != account_data.currency))))
    ).first():
        raise HTTPException(status_code=422, detail='Transfer accounts must share a currency')
    setattr(db_account, 'currency', account_data.currency)
    setattr(db_account, 'name', account_data.name)
    setattr(db_account, 'openingBalance', account_data.openingBalance)
    setattr(db_account, 'openingBalanceDate', account_data.openingBalanceDate)
    if account_data.entries is not None:
        requested_entries = set(account_data.entries)
        current_entries = {
            getattr(item, 'id')
            for item in database.query(Entry).filter(Entry.account_id == db_account.id).all()
        }
        entries_to_detach = current_entries - requested_entries
        if entries_to_detach:
            raise HTTPException(status_code=409, detail="Entry " + ", ".join(str(item) for item in sorted(entries_to_detach)) + " requires a account: reassign it instead of removing it")
        entries_to_attach = requested_entries - current_entries
        for related_entry_id in entries_to_attach:
            related_entry = database.query(Entry).filter(Entry.id == related_entry_id).first()
            if not related_entry:
                raise HTTPException(status_code=400, detail="Entry with id " + str(related_entry_id) + " not found")
        if entries_to_attach:
            database.query(Entry).filter(Entry.id.in_(entries_to_attach)).update(
                {Entry.account_id: db_account.id}, synchronize_session=False
            )
    if account_data.groups is not None:
        existing_related_accountgroup_ids = [assoc._mapping["groups"] for assoc in database.execute(
            groups.select().where(groups.c["accounts"] == db_account.id))]

        related_accountgroups_to_remove = set(existing_related_accountgroup_ids) - set(account_data.groups)
        for related_accountgroup_id in related_accountgroups_to_remove:
            related_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == related_accountgroup_id).first()
            if related_accountgroup is not None and len(related_accountgroup.accounts) - 1 < 1:
                raise HTTPException(status_code=409, detail="AccountGroup " + str(related_accountgroup_id) + " requires at least 1 accounts")
            association = groups.delete().where(
                (groups.c["accounts"] == db_account.id) & (groups.c["groups"] == related_accountgroup_id))
            database.execute(association)

        new_related_accountgroup_ids = set(account_data.groups) - set(existing_related_accountgroup_ids)
        for related_accountgroup_id in new_related_accountgroup_ids:
            related_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == related_accountgroup_id).first()
            if related_accountgroup is None:
                raise HTTPException(status_code=404, detail="AccountGroup with ID " + str(related_accountgroup_id) + " not found")
            if related_accountgroup.accounts and related_accountgroup.accounts[0].currency != account_data.currency:
                raise HTTPException(status_code=422, detail='Consolidated accounts must share a currency')
            association = groups.insert().values(groups=related_accountgroup.id, accounts=db_account.id)
            database.execute(association)
    database.commit()
    database.refresh(db_account)

    related_accountgroup_ids = database.query(groups.c["groups"]).filter(groups.c["accounts"] == db_account.id).all()
    entries_ids = database.query(Entry.id).filter(Entry.account_id == db_account.id).all()
    response_data = {
        "account": db_account,
        "accountgroup_ids": [x[0] for x in related_accountgroup_ids],
        "entries_ids": [x[0] for x in entries_ids]    }
    return response_data


def account_delete_conflict(db_account, deleting=None, wholes=()):
    """Why this Account cannot be deleted (None when it can): a related record
    would be left without a link it requires. Covers the parts deleted with it;
    ``deleting`` holds every record of the delete, since none of them can block it,
    and ``wholes`` the records on the way down to this part."""
    if deleting is None:
        state = sa_inspect(db_account)
        deleting = [db_account] + [item[0] for item in state.mapper.cascade_iterator("delete", state)]
    if sa_inspect(db_account).session.query(Transfer.id).filter(
        (Transfer.fromAccount_id == db_account.id) | (Transfer.toAccount_id == db_account.id)
    ).first() is not None:
        return 'Account has transfers; remove its transfers before deleting it'
    related_entries = db_account.entries
    for related in (list(related_entries) if isinstance(related_entries, list) else [item for item in [related_entries] if item is not None]):
        remaining = 0
        if related not in deleting and remaining < 1:
            return "Entry " + str(getattr(related, 'id')) + " requires at least 1 account"
    related_groups = db_account.groups
    for related in (list(related_groups) if isinstance(related_groups, list) else [item for item in [related_groups] if item is not None]):
        remaining = len(related.accounts) - 1
        if related not in deleting and remaining < 1:
            return "AccountGroup " + str(getattr(related, 'id')) + " requires at least 1 accounts"
    return None


@router.delete("/account/{account_id}/", response_model=None, tags=["Account"])
async def delete_account(account_id: int, database: Session = Depends(get_db)):
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    conflict = account_delete_conflict(db_account)
    if conflict:
        raise HTTPException(status_code=409, detail="Cannot delete Account " + str(account_id) + ": " + conflict)
    # Snapshot the columns before deleting: cascading the association-class
    # links loads relationship collections whose back-references would make
    # the JSON encoder recurse endlessly on the live object.
    deleted_account = {
        attr.key: getattr(db_account, attr.key)
        for attr in db_account.__mapper__.column_attrs
    }
    database.delete(db_account)
    database.commit()
    return deleted_account

@router.post("/account/{account_id}/groups/{accountgroup_id}/", response_model=None, tags=["Account Relationships"])
async def add_groups_to_account(account_id: int, accountgroup_id: int, database: Session = Depends(get_db)):
    """Add a AccountGroup to this Account's groups relationship"""
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    related_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if related_accountgroup is None:
        raise HTTPException(status_code=404, detail="AccountGroup not found")

    # Check if relationship already exists
    existing = database.query(groups).filter(
        (groups.c["accounts"] == account_id) &
        (groups.c["groups"] == accountgroup_id)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")
    if related_accountgroup.accounts and db_account.currency != related_accountgroup.accounts[0].currency:
        raise HTTPException(status_code=422, detail='Consolidated accounts must share a currency')

    # Create the association
    association = groups.insert().values(accounts=account_id, groups=accountgroup_id)
    database.execute(association)
    database.commit()

    return {"message": "AccountGroup added to groups successfully"}


@router.delete("/account/{account_id}/groups/{accountgroup_id}/", response_model=None, tags=["Account Relationships"])
async def remove_groups_from_account(account_id: int, accountgroup_id: int, database: Session = Depends(get_db)):
    """Remove a AccountGroup from this Account's groups relationship"""
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    # Check if relationship exists
    existing = database.query(groups).filter(
        (groups.c["accounts"] == account_id) &
        (groups.c["groups"] == accountgroup_id)
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Relationship not found")

    related_accountgroup = database.query(AccountGroup).filter(AccountGroup.id == accountgroup_id).first()
    if related_accountgroup is not None and len(related_accountgroup.accounts) - 1 < 1:
        raise HTTPException(status_code=409, detail="AccountGroup " + str(accountgroup_id) + " requires at least 1 accounts")

    # Delete the association
    association = groups.delete().where(
        (groups.c["accounts"] == account_id) &
        (groups.c["groups"] == accountgroup_id)
    )
    database.execute(association)
    database.commit()

    return {"message": "AccountGroup removed from groups successfully"}


@router.get("/account/{account_id}/groups/", response_model=None, tags=["Account Relationships"])
async def get_groups_of_account(account_id: int, database: Session = Depends(get_db)):
    """Get all AccountGroup entities related to this Account through groups"""
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    related_accountgroup_ids = database.query(groups.c["groups"]).filter(groups.c["accounts"] == account_id).all()
    related_accountgroup_list = database.query(AccountGroup).filter(AccountGroup.id.in_([id[0] for id in related_accountgroup_ids])).all()

    return {
        "account_id": account_id,
        "groups_count": len(related_accountgroup_list),
        "groups": related_accountgroup_list
    }


@router.get("/account/{account_id}/entries/", response_model=None, tags=["Account Relationships"])
async def get_entries_of_account(account_id: int, database: Session = Depends(get_db)):
    """Get all Entry entities related to this Account through entries"""
    db_account = database.query(Account).filter(Account.id == account_id).first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    entries_list = database.query(Entry).filter(Entry.account_id == account_id).all()

    return {
        "account_id": account_id,
        "entries_count": len(entries_list),
        "entries": entries_list
    }


