import enum
import os
# Both spellings are bound on purpose. Generated code uses the trailing-
# underscore aliases so a modelled class named List, Optional or DateTime
# cannot shadow them. The PLAIN names are imported too because this file is
# routinely edited afterwards by an LLM, which writes ordinary Python and has
# no reason to know about the aliasing convention; without the plain names
# such edits fail to import:
#
#     Mapped_[Optional[int]]        undefined name 'Optional'
#     mapped_column(DateTime())     undefined name 'DateTime'
#
# so every aliased name below is bound both ways.
from typing import List, Optional, List as List_, Optional as Optional_
from sqlalchemy import (
    create_engine, Enum, UniqueConstraint as _UniqueConstraint, event as _sa_event,
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Interval,
    PickleType, String, Table, Text, Time,
    Column as Column_, ForeignKey as ForeignKey_, Table as Table_,
    Text as Text_, Boolean as Boolean_, String as String_, Date as Date_,
    Time as Time_, DateTime as DateTime_, Float as Float_, Integer as Integer_,
    Interval as Interval_, PickleType as PickleType_,
)
from sqlalchemy.ext.declarative import AbstractConcreteBase
from sqlalchemy.orm import (
    column_property, DeclarativeBase, Mapped, Mapped as Mapped_, mapped_column,
    relationship
)
from datetime import datetime as dt_datetime, time as dt_time, date as dt_date, timedelta as dt_timedelta
from uuid import uuid4 as _uuid4


def _new_str_id() -> str:
    """Server-side surrogate for string primary keys named ``id``.

    A string PK has no autoincrement; without a default every INSERT dies
    on NOT NULL (the id is in nobody's hands: create schemas rightly
    exclude the server-owned ``id``, so the server must mint it).
    """
    return _uuid4().hex


def _configure_sqlite_engine(engine):
    """Enforce declared foreign keys on every SQLite connection."""
    if engine.dialect.name == "sqlite":
        @_sa_event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection, _record):
            previous_autocommit = getattr(connection, "autocommit", None)
            if previous_autocommit is not None:
                connection.autocommit = True
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()
                if previous_autocommit is not None:
                    connection.autocommit = previous_autocommit


class Base(DeclarativeBase):
    pass

# Definitions of Enumerations
class ExpenseType(enum.Enum):
    FIX = "FIX"
    VARIABLE = "VARIABLE"
    EXTRAORDINARY = "EXTRAORDINARY"


# Tables definition for many-to-many relationships
groups = Table_(
    "groups",
    Base.metadata,
    Column_("accounts", ForeignKey_("account.id"), primary_key=True),
    Column_("groups", ForeignKey_("accountgroup.id"), primary_key=True),
)

# Tables definition
class Entry(Base):
    __tablename__ = "entry"
    id: Mapped_[int] = mapped_column(primary_key=True)
    description: Mapped_[str] = mapped_column(String_(100))
    amount: Mapped_[float] = mapped_column(Float_)
    startDate: Mapped_[dt_date] = mapped_column(Date_)
    endDate: Mapped_[Optional_[dt_date]] = mapped_column(Date_, nullable=True)
    recurrenceIntervalMonths: Mapped_[Optional_[int]] = mapped_column(Integer_, nullable=True)
    account_id: Mapped_[int] = mapped_column(ForeignKey_("account.id"))
    category_id: Mapped_[Optional_[int]] = mapped_column(ForeignKey_("category.id"), nullable=True)
    type_spec: Mapped_[str] = mapped_column(String_(50))
    __mapper_args__ = {
        "polymorphic_identity": "entry",
        "polymorphic_on": "type_spec",
    }

class Revenue(Entry):
    __tablename__ = "revenue"
    id: Mapped_[int] = mapped_column(ForeignKey_("entry.id"), primary_key=True)
    __mapper_args__ = {
        "polymorphic_identity": "revenue",
    }

class Expense(Entry):
    __tablename__ = "expense"
    id: Mapped_[int] = mapped_column(ForeignKey_("entry.id"), primary_key=True)
    expenseType: Mapped_[ExpenseType] = mapped_column(Enum(ExpenseType))
    __mapper_args__ = {
        "polymorphic_identity": "expense",
    }

class Transfer(Base):
    __tablename__ = "transfer"
    id: Mapped_[int] = mapped_column(primary_key=True)
    fromAccount_id: Mapped_[int] = mapped_column(ForeignKey_("account.id"), nullable=False)
    toAccount_id: Mapped_[int] = mapped_column(ForeignKey_("account.id"), nullable=False)
    amount: Mapped_[float] = mapped_column(Float_, nullable=False)
    date: Mapped_[dt_date] = mapped_column(Date_, nullable=False)
    description: Mapped_[str] = mapped_column(String_(100), default="")
    recurrenceIntervalMonths: Mapped_[Optional_[int]] = mapped_column(Integer_, nullable=True)
    endDate: Mapped_[Optional_[dt_date]] = mapped_column(Date_, nullable=True)


class Category(Base):
    __tablename__ = "category"
    id: Mapped_[int] = mapped_column(primary_key=True)
    name: Mapped_[str] = mapped_column(String_(100))
    kind: Mapped_[str] = mapped_column(String_(10), nullable=False)

class AccountGroup(Base):
    __tablename__ = "accountgroup"
    id: Mapped_[int] = mapped_column(primary_key=True)
    name: Mapped_[str] = mapped_column(String_(100))

class Account(Base):
    __tablename__ = "account"
    id: Mapped_[int] = mapped_column(primary_key=True)
    name: Mapped_[str] = mapped_column(String_(100))
    openingBalance: Mapped_[float] = mapped_column(Float_)
    openingBalanceDate: Mapped_[dt_date] = mapped_column(Date_)
    currency: Mapped_[str] = mapped_column(String_(100))


#--- Relationships of the entry table

Entry.account: Mapped_["Account"] = relationship("Account", back_populates="entries", uselist=False, foreign_keys=[Entry.account_id])

Entry.category: Mapped_["Category"] = relationship("Category", back_populates="entries", uselist=False, foreign_keys=[Entry.category_id])

#--- Relationships of the category table
Category.entries: Mapped_[List_["Entry"]] = relationship("Entry", back_populates="category", foreign_keys=[Entry.category_id])

#--- Relationships of the accountgroup table
AccountGroup.accounts: Mapped_[List_["Account"]] = relationship("Account", secondary=groups, back_populates="groups")

#--- Relationships of the account table
Account.entries: Mapped_[List_["Entry"]] = relationship("Entry", back_populates="account", foreign_keys=[Entry.account_id])
Account.groups: Mapped_[List_["AccountGroup"]] = relationship("AccountGroup", secondary=groups, back_populates="accounts")

# Database connection (override the default with the DATABASE_URL environment variable)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/Class_Diagram_2.db")  # SQLite connection
engine = create_engine(DATABASE_URL)
_configure_sqlite_engine(engine)

if __name__ == "__main__":
    # Create tables in the database only when this module is executed directly,
    # so importing it never touches the database as a side effect.
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)  # folder for the default SQLite database
    Base.metadata.create_all(engine, checkfirst=True)