"""Fixtures for the service tests (tests/unit/Services).

The services run against the isolated SQLite test database of the repository tests (tests/unit/Data/conftest.py):
every test gets a fresh in-memory copy holding the `bank` rows, and a real, active unit of work on it. Interactions
are observed with a spy on save_changes_async and with the SQL the engine executes; pure interaction and dependency
injection tests use mocks of the unit of work, its repositories and the collaborating services instead.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import event, select

from Data.Interfaces.i_repository import IRepository
from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Constants.AppConstants import AppConstants
from Models.Entities import Account, Customer, Transaction
from Services.Implementations.AccountService import AccountService
from Services.Implementations.AccountTypeService import AccountTypeService
from Services.Implementations.CustomerService import CustomerService
from Services.Implementations.StaffService import StaffService
from Services.Implementations.UserService import UserService
from Services.Implementations.transaction_service import TransactionService
# The database fixtures of the repository tests (imported, not copied, so both suites use the same test database).
from tests.unit.Data.conftest import (bank, database_name, engine, persisted, seeded_template,  # noqa: F401
                                      session_factory, unit_of_work)

# Applied by every service test module: SQLAlchemy warnings point at ORM misuse and fail the test; SQLite's note that
# it stores DECIMAL as a floating point number is expected. (The async tests carry pytest.mark.asyncio themselves,
# so that the synchronous contract tests in the same module are not marked.)
SERVICE_TEST_MARKS = [pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning"),
                      pytest.mark.filterwarnings("ignore:Dialect sqlite\\+aiosqlite does \\*not\\* support Decimal")]


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """Users are created with real bcrypt hashes at the lowest cost (2^4 rounds instead of 2^12): the hashes are
    verified the same way, the tests just do not spend a quarter of a second per user. The production cost is covered
    by tests/unit/Infrastructure/test_Security.py."""
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")


@pytest.fixture(autouse=True)
def seeded_lookups_match_the_constants(bank):
    """The services refer to lookup rows by the identifiers in AppConstants: the test database must use them too."""
    assert bank.role_ids == {"Customer": AppConstants.CustomerRoleId, "Staff": AppConstants.StaffRoleId}
    assert bank.account_type_ids["Savings"] == AppConstants.SavingsAccountTypeId
    assert bank.account_type_ids["Current"] == AppConstants.CurrentAccountTypeId
    assert bank.transaction_type_ids == {"Deposit": AppConstants.DepositTransactionTypeId,
                                         "Transfer": AppConstants.TransferTransactionTypeId}
    assert bank.transaction_mode_ids == {"Credit": AppConstants.CreditTransactionModeId,
                                         "Debit": AppConstants.DebitTransactionModeId}
    assert bank.transaction_status_ids["Completed"] == AppConstants.CompletedTransactionStatusId


# ---------------------------------------------------------------------------
# Services (wired as Infrastructure/DependencyInjection/container.py wires them)
# ---------------------------------------------------------------------------

@pytest.fixture
def user_service():
    return UserService()


@pytest.fixture
def staff_service(user_service):
    return StaffService(user_service)


@pytest.fixture
def customer_service(user_service):
    return CustomerService(user_service)


@pytest.fixture
def account_type_service():
    return AccountTypeService()


@pytest.fixture
def account_service():
    return AccountService()


@pytest.fixture
def transaction_service():
    return TransactionService()


# ---------------------------------------------------------------------------
# Observing the unit of work and the database
# ---------------------------------------------------------------------------

@pytest.fixture
def save_spy(unit_of_work, monkeypatch):
    """Counts the unit of work's save_changes_async() calls; the calls still save."""
    spy = AsyncMock(wraps=unit_of_work.save_changes_async)
    monkeypatch.setattr(unit_of_work, "save_changes_async", spy)
    return spy


@pytest.fixture
def sql_statements(engine):
    """The SQL statements the engine executes from now on (whitespace collapsed, identifier quotes removed)."""
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.replace('"', "").split()))

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    yield statements
    event.remove(engine.sync_engine, "before_cursor_execute", record)


@pytest.fixture
def failing_trigger(engine):
    """Install a trigger that makes the database refuse a statement (as a broken constraint would), to check that an
    operation is saved all or nothing: ``await failing_trigger("BEFORE INSERT ON Accounts")``."""

    async def _install(timing_and_table):
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                f"CREATE TRIGGER refuse_in_test {timing_and_table} BEGIN SELECT RAISE(ABORT, 'refused by test'); END")

    return _install


@pytest.fixture
def customer_ids(persisted, bank):
    """Customers.Id by first name (the `bank` rows only know the users)."""

    async def _customer_ids():
        customers = await persisted.all(select(Customer))
        by_user = {customer.UserId: customer.Id for customer in customers}
        return {name: by_user[user_id] for name, user_id in bank.user_ids.items() if user_id in by_user}

    return _customer_ids


@pytest.fixture
def add_transaction(persisted, session_factory, bank):
    """Commit a completed transaction on an account (outside the unit of work under test)."""

    async def _add_transaction(account_number, amount="10.00", sender=None, type_name="Deposit", mode_name="Credit"):
        account = bank.accounts[account_number]
        async with session_factory() as session:
            transaction = Transaction(AccountId=account.id, UserId=bank.user_ids[account.owner],
                                      TransactionTypeId=bank.transaction_type_ids[type_name],
                                      TransactionModeId=bank.transaction_mode_ids[mode_name],
                                      TransactionStatusId=bank.transaction_status_ids["Completed"],
                                      Amount=Decimal(amount), SenderId=sender)
            session.add(transaction)
            await session.commit()
            return transaction.Id

    return _add_transaction


@pytest.fixture
def deactivate_account(session_factory, bank):
    """Deactivate one account (committed, outside the unit of work under test); its owner stays active."""

    async def _deactivate_account(account_number):
        async with session_factory() as session:
            account = await session.get(Account, bank.account_id(account_number))
            account.Active = False
            await session.commit()

    return _deactivate_account


# Personal and account data that error messages must not repeat (they may reach API clients and logs).
PERSONAL_DATA = ["@example.com", *(f"26000000{number:02d}" for number in range(1, 6)), "2699999999"]


def assert_no_personal_data(message):
    assert not [value for value in PERSONAL_DATA if value in message], message


@pytest.fixture
def balances(persisted):
    """{account number: committed balance}."""

    async def _balances():
        return {account.AccountNumber: account.Balance for account in await persisted.all(select(Account))}

    return _balances


# ---------------------------------------------------------------------------
# Mocks (no database)
# ---------------------------------------------------------------------------

REPOSITORY_NAMES = ["roles", "users", "staff", "customers", "account_types", "accounts", "transaction_types",
                    "transaction_modes", "transaction_statuses", "transactions"]


@pytest.fixture
def mock_unit_of_work():
    """A unit of work whose repositories are mocks of IRepository (awaitable methods are AsyncMocks) and whose
    save_changes_async is an AsyncMock. Staging methods return the entity they are given, as the repository does."""
    unit_of_work = MagicMock(spec=IUnitOfWork)
    for name in REPOSITORY_NAMES:
        repository = MagicMock(spec=IRepository)
        repository.add_single.side_effect = lambda entity: entity
        repository.update_single.side_effect = lambda entity, values=None: entity
        setattr(unit_of_work, name, repository)
    unit_of_work.save_changes_async = AsyncMock()
    return unit_of_work
