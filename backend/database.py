import os
import logging
import re
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sql_alchemy import Base, _configure_sqlite_engine

logger = logging.getLogger(__name__)

############################################
#
#   Initialize the database
#
############################################

def init_db():
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/Class_Diagram_2.db")
    # check_same_thread is a SQLite-only argument; do not pass it to other drivers
    connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        # Folder for the default local SQLite database; other DBMS need no local directory
        os.makedirs("data", exist_ok=True)
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args=connect_args,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False
    )
    _configure_sqlite_engine(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    # Existing SQLite databases predate optional entry categories. Rebuild only
    # that column's nullability, retaining rows, indexes, and foreign keys.
    if engine.dialect.name == 'sqlite':
        with engine.begin() as connection:
            columns = connection.exec_driver_sql('PRAGMA table_info(entry)').fetchall()
            if columns and any(col[1] == 'category_id' and col[3] for col in columns):
                original = connection.exec_driver_sql(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='entry'").scalar()
                updated = re.sub(r'(?i)(category_id\s+INTEGER)\s+NOT NULL', r'\1', original)
                if updated == original:
                    raise RuntimeError('Cannot migrate entry.category_id nullability')
                connection.exec_driver_sql('PRAGMA writable_schema=ON')
                try:
                    connection.exec_driver_sql(
                        "UPDATE sqlite_master SET sql=? WHERE type='table' AND name='entry'", (updated,))
                finally:
                    connection.exec_driver_sql('PRAGMA writable_schema=OFF')
                connection.exec_driver_sql('PRAGMA schema_version = ' + str(
                    connection.exec_driver_sql('PRAGMA schema_version').scalar() + 1))
            category_columns = {col[1] for col in connection.exec_driver_sql('PRAGMA table_info(category)')}
            if 'kind' not in category_columns:
                connection.exec_driver_sql("ALTER TABLE category ADD COLUMN kind VARCHAR(10) NOT NULL DEFAULT 'expense'")
                # Existing categories were shared; preserve their expense references,
                # and give revenue references their own category records.
                categories = connection.exec_driver_sql('SELECT id, name FROM category').fetchall()
                for category_id, name in categories:
                    if connection.exec_driver_sql(
                        "SELECT 1 FROM entry WHERE category_id=? AND type_spec='revenue' LIMIT 1", (category_id,)
                    ).first():
                        result = connection.exec_driver_sql(
                            "INSERT INTO category (name, kind) VALUES (?, 'revenue')", (name,))
                        connection.exec_driver_sql(
                            "UPDATE entry SET category_id=? WHERE category_id=? AND type_spec='revenue'",
                            (result.lastrowid, category_id))
                        if not connection.exec_driver_sql(
                            'SELECT 1 FROM entry WHERE category_id=? LIMIT 1', (category_id,)
                        ).first():
                            connection.exec_driver_sql('DELETE FROM category WHERE id=?', (category_id,))
            # Rename the discriminator and category kind without replacing existing data.
            connection.exec_driver_sql("UPDATE entry SET type_spec='income' WHERE type_spec='revenue'")
            connection.exec_driver_sql("UPDATE category SET kind='income' WHERE kind='revenue'")
            income_columns = {col[1] for col in connection.exec_driver_sql('PRAGMA table_info(revenue)')}
            if 'incomeType' not in income_columns:
                connection.exec_driver_sql("ALTER TABLE revenue ADD COLUMN \"incomeType\" VARCHAR(20) NOT NULL DEFAULT 'EXTRAORDINARY'")
            expense_columns = {col[1] for col in connection.exec_driver_sql('PRAGMA table_info(expense)')}
            if 'expectedValue' not in expense_columns:
                connection.exec_driver_sql('ALTER TABLE expense ADD COLUMN "expectedValue" FLOAT')
            if 'allowedDeviation' not in expense_columns:
                connection.exec_driver_sql('ALTER TABLE expense ADD COLUMN "allowedDeviation" FLOAT')
            transfer_columns = {col[1] for col in connection.exec_driver_sql('PRAGMA table_info(transfer)')}
            if 'recurrenceIntervalMonths' not in transfer_columns:
                connection.exec_driver_sql('ALTER TABLE transfer ADD COLUMN "recurrenceIntervalMonths" INTEGER')
            if 'endDate' not in transfer_columns:
                connection.exec_driver_sql('ALTER TABLE transfer ADD COLUMN "endDate" DATE')
    return SessionLocal

# Initialize database session
SessionLocal = init_db()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        # A 4xx answer is the client's mistake, not a failure of the server.
        client_error = isinstance(exc, RequestValidationError) or (
            isinstance(exc, HTTPException) and exc.status_code < 500)
        if not client_error:
            logger.error("Database session rollback due to exception")
        raise
    finally:
        db.close()


def integrity_error_detail(exc) -> str:
    """What a constraint violation tells the client.

    A duplicate value or a broken reference gets a sentence, naming the class
    and field when the driver names them. Any other violation keeps the first
    line of the driver's text, which classifies it ("NOT NULL constraint
    failed: book.title"). PostgreSQL's DETAIL line and those after it can
    carry the values of the rejected row, in any language.
    """
    driver_text = str(getattr(exc, "orig", exc))
    lowered = driver_text.lower()
    if any(phrase in lowered for phrase in ("unique constraint", "duplicate key", "duplicate entry")):
        class_names = {mapper.local_table.name: mapper.class_.__name__ for mapper in Base.registry.mappers}
        fields = [
            (class_names.get(table.name, table.name), column.name)
            for table in Base.metadata.tables.values()
            for column in table.columns
            if re.search(rf"(?<![\w.]){re.escape(table.name)}\.{re.escape(column.name)}(?!\w)", driver_text)
            or f'"{table.name}_{column.name}_key"' in driver_text
        ]
        if len(fields) == 1:
            return f"{fields[0][0]} with this {fields[0][1]} already exists"
        return "A record with the same values already exists"
    if "foreign key constraint" in lowered:
        return "The record refers to a record that does not exist, or another record still refers to it"
    return re.split(r"\n|\s*DETAIL:", driver_text, maxsplit=1)[0]