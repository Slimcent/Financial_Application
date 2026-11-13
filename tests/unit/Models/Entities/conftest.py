"""Shared fixtures for the entity (SQLAlchemy mapping) tests.

These tests inspect the mapped classes and their metadata, compile DDL offline and use a Session without an
engine. They never connect to a database.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session, configure_mappers, make_transient_to_detached

from Models.Entities import (
    Account,
    AccountType,
    Customer,
    Role,
    Staff,
    Transaction,
    TransactionMode,
    TransactionStatus,
    TransactionType,
    User,
)
from Models.Entities.column_types import uuid7

AUDIT_COLUMNS = ("CreatedAt", "UpdatedAt", "CreatedBy", "UpdatedBy")

# Main entities have GUID (UUIDv7, CHAR(32)) keys; lookup / selection entities have integer keys.
GUID_KEY_ENTITIES = [User, Customer, Staff, Account, Transaction]
INTEGER_KEY_ENTITIES = [Role, AccountType, TransactionType, TransactionMode, TransactionStatus]
ALL_ENTITIES = GUID_KEY_ENTITIES + INTEGER_KEY_ENTITIES

MYSQL = mysql.dialect()


@pytest.fixture(scope="session", autouse=True)
def configured_mappers():
    configure_mappers()


# ---------------------------------------------------------------------------
# Entity parameters (each test using one runs once per entity)
# ---------------------------------------------------------------------------

@pytest.fixture(params=ALL_ENTITIES, ids=lambda entity: entity.__name__)
def entity(request):
    return request.param


@pytest.fixture(params=GUID_KEY_ENTITIES, ids=lambda entity: entity.__name__)
def guid_key_entity(request):
    return request.param


@pytest.fixture(params=INTEGER_KEY_ENTITIES, ids=lambda entity: entity.__name__)
def integer_key_entity(request):
    return request.param


@pytest.fixture
def all_entities():
    return list(ALL_ENTITIES)


# ---------------------------------------------------------------------------
# Schema description of one entity, in a form that is easy to compare with the expected definition
# ---------------------------------------------------------------------------

@pytest.fixture
def mysql_type():
    """The MySQL DDL type of a column, e.g. "CHAR(32)" or "DECIMAL(18, 2)"."""

    def _mysql_type(column):
        return str(column.type.compile(dialect=MYSQL))

    return _mysql_type


@pytest.fixture
def column_definitions(mysql_type):
    """{column: (MySQL type, nullable)} for the columns an entity declares itself (shared audit columns excluded)."""

    def _column_definitions(entity):
        return {column.name: (mysql_type(column), column.nullable)
                for column in entity.__table__.columns if column.name not in AUDIT_COLUMNS}

    return _column_definitions


@pytest.fixture
def relationship_definitions():
    """{relationship: (target entity, direction, uselist, back_populates, join column pairs)}."""

    def _relationship_definitions(entity):
        return {
            rel.key: (rel.mapper.class_.__name__, rel.direction.name, rel.uselist, rel.back_populates,
                      frozenset(f"{local.table.name}.{local.name}={remote.table.name}.{remote.name}"
                                for local, remote in rel.local_remote_pairs))
            for rel in inspect(entity).relationships
        }

    return _relationship_definitions


@pytest.fixture
def foreign_keys_of():
    """{(local columns): (referenced table, (referenced columns))}."""

    def _foreign_keys_of(entity):
        return {tuple(fk.column_keys): (fk.referred_table.name, tuple(element.column.name for element in fk.elements))
                for fk in entity.__table__.foreign_key_constraints}

    return _foreign_keys_of


@pytest.fixture
def unique_constraints_of():
    """The column tuples of an entity's unique constraints (column-level unique=True included)."""

    def _unique_constraints_of(entity):
        return {tuple(column.name for column in constraint.columns)
                for constraint in entity.__table__.constraints if isinstance(constraint, UniqueConstraint)}

    return _unique_constraints_of


@pytest.fixture
def indexes_of():
    """The column tuples of an entity's (non-unique) indexes."""

    def _indexes_of(entity):
        return {tuple(column.name for column in index.columns) for index in entity.__table__.indexes}

    return _indexes_of


@pytest.fixture
def check_constraints_of():
    """{constraint name: SQL condition}."""

    def _check_constraints_of(entity):
        return {constraint.name: str(constraint.sqltext)
                for constraint in entity.__table__.constraints if isinstance(constraint, CheckConstraint)}

    return _check_constraints_of


# ---------------------------------------------------------------------------
# ORM behaviour without a database
# ---------------------------------------------------------------------------

@pytest.fixture
def fire_before_insert():
    """Run the entity's before_insert mapper events on `obj`, as a flush would, and return it."""

    def _fire_before_insert(obj):
        mapper = inspect(type(obj))
        mapper.dispatch.before_insert(mapper, None, inspect(obj))
        return obj

    return _fire_before_insert


@pytest.fixture
def session_without_database():
    """A Session with no engine: anything that needs SQL could not even get a connection."""
    with Session() as session:
        yield session


@pytest.fixture
def loaded_graph(session_without_database):
    """A consistent set of rows, made persistent in the engine-less session as if they had been loaded.

    Only the columns are set; no relationship is loaded, so reading one shows what the loader strategy does.
    """
    role = Role(Id=1, Name="Customer")
    account_type = AccountType(Id=1, Type="Savings")
    transaction_type, transaction_mode, transaction_status = (
        TransactionType(Id=1, Name="Deposit"), TransactionMode(Id=1, Name="Credit"),
        TransactionStatus(Id=2, Name="Completed"))
    user = User(Id=uuid7(), LastName="Doe", FirstName="Jane", Email="example@example.com", RoleId=role.Id,
                Password="hash", Active=True)
    staff = Staff(Id=uuid7(), UserId=user.Id, Position="Teller")
    customer = Customer(Id=uuid7(), UserId=user.Id, Address="1 Main Street")
    account = Account(Id=uuid7(), UserId=user.Id, AccountTypeId=account_type.Id, AccountNumber="2606387058",
                      Balance=Decimal("100.00"))
    transaction = Transaction(Id=uuid7(), AccountId=account.Id, UserId=user.Id, SenderId=None,
                              TransactionTypeId=transaction_type.Id, TransactionModeId=transaction_mode.Id,
                              TransactionStatusId=transaction_status.Id, Amount=Decimal("5.00"))
    graph = {"role": role, "account_type": account_type, "transaction_type": transaction_type,
             "transaction_mode": transaction_mode, "transaction_status": transaction_status, "user": user,
             "staff": staff, "customer": customer, "account": account, "transaction": transaction}
    for obj in graph.values():
        make_transient_to_detached(obj)
        session_without_database.add(obj)
    return graph


@pytest.fixture
def orphan_transaction(session_without_database):
    """A loaded transaction whose account, user and lookups are not in the session."""
    transaction = Transaction(Id=uuid7(), AccountId=uuid.UUID(int=1), UserId=uuid.UUID(int=2), SenderId=uuid.UUID(int=3),
                              TransactionTypeId=1, TransactionModeId=1, TransactionStatusId=1, Amount=Decimal("1.00"))
    make_transient_to_detached(transaction)
    session_without_database.add(transaction)
    return transaction
