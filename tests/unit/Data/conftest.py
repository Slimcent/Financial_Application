"""Fixtures shared by the repository and unit of work tests (tests/unit/Data/Repository, tests/unit/Data/UnitOfWork).

Every test gets its own SQLite in-memory database with the full schema from Models/Entities, foreign keys
enforced and a small, known set of committed rows (described by the `bank` fixture). No MySQL database is needed.

The schema and the rows are built once per test session in a template database; each test starts from a fresh copy
of it (SQLite backup API), so tests never see each other's changes. Each copy is a shared-cache in-memory database:
the code under test uses an async engine (aiosqlite) with a real connection pool on it, and the unit of work's
session and the `persisted` reader use different connections - what `persisted` sees is what was committed.
"""
import inspect
import sqlite3
import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import AsyncAdaptedQueuePool, StaticPool

from Data.Implementations.unit_of_work import UnitofWork
from Models.Entities import (Account, AccountType, Base, Customer, Role, Staff, Transaction, TransactionMode,
                             TransactionStatus, TransactionType, User)

USERS = {
    # first name: (last name, role)
    "Ada": ("Lovelace", "Customer"),
    "Ben": ("Okafor", "Customer"),
    "Cy": ("Young", "Customer"),
    "Dee": ("Mensah", "Staff"),
}

# (account number, owner, account type, balance). Created in this order, so the (time-ordered) primary keys
# ascend in this order too.
ACCOUNTS = [
    ("2600000001", "Ada", "Savings", "100.00"),
    ("2600000002", "Ada", "Current", "50.00"),
    ("2600000003", "Ben", "Savings", "200.00"),
    ("2600000004", "Cy", "Savings", "0.00"),
    ("2600000005", "Dee", "Current", "75.00"),
]

# (account number, amount): completed credit deposits.
TRANSACTIONS = [
    ("2600000001", "100.00"),
    ("2600000003", "200.00"),
]


# (owner, account type) pairs without a seeded account: a user has at most one account per account type.
FREE_ACCOUNT_SLOTS = [("Cy", "Current"), ("Cy", "Retirement"), ("Ben", "Current"), ("Ben", "Retirement"),
                      ("Ada", "Retirement"), ("Dee", "Savings"), ("Dee", "Retirement")]


@dataclass(frozen=True)
class SeededAccount:
    id: uuid.UUID
    number: str
    owner: str
    account_type: str
    balance: Decimal


@dataclass(frozen=True)
class Bank:
    """Identifiers of the rows the `bank` fixture commits before each test."""

    role_ids: dict[str, int]
    account_type_ids: dict[str, int]
    transaction_type_ids: dict[str, int]
    transaction_mode_ids: dict[str, int]
    transaction_status_ids: dict[str, int]
    user_ids: dict[str, uuid.UUID]
    accounts: dict[str, SeededAccount]   # by account number
    transaction_ids: list[uuid.UUID]

    def account_id(self, number: str) -> uuid.UUID:
        return self.accounts[number].id

    @property
    def account_numbers(self) -> list[str]:
        """In primary-key order."""
        return sorted(self.accounts, key=lambda number: self.accounts[number].id.hex)


class Persisted:
    """Reads what is committed in the database, through sessions of its own (never the unit of work's)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, model, entity_id):
        async with self._session_factory() as session:
            return await session.get(model, entity_id)

    async def all(self, statement):
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    async def count(self, model, *criteria) -> int:
        async with self._session_factory() as session:
            return await session.scalar(select(func.count()).select_from(model).where(*criteria))

    async def scalar(self, statement):
        async with self._session_factory() as session:
            return await session.scalar(statement)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _url(driver, database_name):
    return f"{driver}:///file:{database_name}?mode=memory&cache=shared&uri=true"


def _enforce_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _open_keeper(database_name):
    """An in-memory database exists while a connection to it is open: this one stays open while it is needed,
    outside the connection pool the tests look at."""
    return sqlite3.connect(f"file:{database_name}?mode=memory&cache=shared", uri=True)


@pytest.fixture(scope="session")
def seeded_template():
    """(keeper connection, Bank): the full schema and the seed rows, built once per test session."""
    name = f"data_tests_template_{uuid.uuid4().hex}"
    keeper = _open_keeper(name)
    template_engine = create_engine(_url("sqlite", name), poolclass=StaticPool)
    event.listen(template_engine, "connect", _enforce_foreign_keys)
    Base.metadata.create_all(template_engine, checkfirst=False)
    seeded = _seed(template_engine)
    template_engine.dispose()
    yield keeper, seeded
    keeper.close()


@pytest.fixture
def database_name(seeded_template):
    """A fresh copy of the seeded template database, for one test."""
    template, _ = seeded_template
    name = f"data_tests_{uuid.uuid4().hex}"
    keeper = _open_keeper(name)
    template.backup(keeper)
    yield name
    keeper.close()


@pytest_asyncio.fixture
async def engine(database_name):
    """The async engine the code under test uses: aiosqlite, a real connection pool, foreign keys enforced."""
    test_engine = create_async_engine(_url("sqlite+aiosqlite", database_name), poolclass=AsyncAdaptedQueuePool)
    event.listen(test_engine.sync_engine, "connect", _enforce_foreign_keys)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    """Sessions configured like the application's (Data/database_orm_async.py), on the test database."""
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def persisted(session_factory):
    return Persisted(session_factory)


@pytest.fixture
def bank(seeded_template):
    """The identifiers of the rows every test database starts with: lookups, four users (three customers, one
    staff), five accounts and two transactions (see USERS, ACCOUNTS and TRANSACTIONS)."""
    return seeded_template[1]


def _seed(seed_engine):
    with Session(seed_engine, expire_on_commit=False) as session:
        roles = {name: Role(Name=name) for name in ("Customer", "Staff")}
        account_types = {name: AccountType(Type=name) for name in ("Savings", "Current", "Retirement")}
        transaction_types = {name: TransactionType(Name=name) for name in ("Deposit", "Transfer")}
        transaction_modes = {name: TransactionMode(Name=name) for name in ("Credit", "Debit")}
        transaction_statuses = {name: TransactionStatus(Name=name) for name in ("Pending", "Completed")}
        session.add_all([*roles.values(), *account_types.values(), *transaction_types.values(),
                         *transaction_modes.values(), *transaction_statuses.values()])
        session.flush()

        users = {}
        for first_name, (last_name, role) in USERS.items():
            users[first_name] = User(LastName=last_name, FirstName=first_name, Email=f"{first_name.lower()}@example.com",
                                     RoleId=roles[role].Id, Password="hash")
            session.add(users[first_name])
            session.flush()
            if role == "Customer":
                session.add(Customer(UserId=users[first_name].Id, Address=f"{first_name} Street"))
            else:
                session.add(Staff(UserId=users[first_name].Id, Position="Teller"))

        accounts = {}
        for number, owner, account_type, balance in ACCOUNTS:
            accounts[number] = Account(UserId=users[owner].Id, AccountTypeId=account_types[account_type].Id,
                                       AccountNumber=number, Balance=Decimal(balance))
            session.add(accounts[number])
            session.flush()

        transactions = []
        for number, amount in TRANSACTIONS:
            transaction = Transaction(AccountId=accounts[number].Id, UserId=accounts[number].UserId,
                                      TransactionTypeId=transaction_types["Deposit"].Id,
                                      TransactionModeId=transaction_modes["Credit"].Id,
                                      TransactionStatusId=transaction_statuses["Completed"].Id,
                                      Amount=Decimal(amount), Description="opening deposit")
            session.add(transaction)
            session.flush()
            transactions.append(transaction)
        session.commit()

    return Bank(
        role_ids={name: role.Id for name, role in roles.items()},
        account_type_ids={name: account_type.Id for name, account_type in account_types.items()},
        transaction_type_ids={name: item.Id for name, item in transaction_types.items()},
        transaction_mode_ids={name: item.Id for name, item in transaction_modes.items()},
        transaction_status_ids={name: item.Id for name, item in transaction_statuses.items()},
        user_ids={name: user.Id for name, user in users.items()},
        accounts={number: SeededAccount(id=account.Id, number=number, owner=owner, account_type=account_type,
                                        balance=Decimal(balance))
                  for (number, owner, account_type, balance), account in zip(ACCOUNTS, accounts.values())},
        transaction_ids=[transaction.Id for transaction in transactions],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def result_of():
    """The result of a repository call: awaited for the `_async` operations, as is for the others.

    Lets one parametrized test cover a staging operation and its `_async` form, e.g.
    `await result_of(operation(repository))`.
    """

    async def _result_of(call_result):
        return await call_result if inspect.isawaitable(call_result) else call_result

    return _result_of


# ---------------------------------------------------------------------------
# Unit of work
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def unit_of_work(session_factory):
    """An active unit of work on the test database."""
    async with UnitofWork(session_factory) as active_unit_of_work:
        yield active_unit_of_work


@pytest.fixture
def new_account(bank):
    """Build a new (unsaved) account. Each call takes the next free (owner, account type) pair and a new account
    number, so accounts built in one test never collide."""
    slots = iter(FREE_ACCOUNT_SLOTS)
    numbers = iter(range(2700000001, 2800000000))

    def _new_account(balance="10.00", **values):
        """`balance=None` leaves the balance unset, so the column default applies."""
        owner, account_type = next(slots)
        if balance is not None:
            values["Balance"] = Decimal(balance)
        return Account(UserId=bank.user_ids[owner], AccountTypeId=bank.account_type_ids[account_type],
                       AccountNumber=str(next(numbers)), **values)

    return _new_account


@pytest.fixture
def new_role():
    """Build a new (unsaved) role; names are unique per call unless given."""
    names = iter(range(1, 1_000_000))

    def _new_role(name=None):
        return Role(Name=name or f"Role {next(names)}")

    return _new_role
